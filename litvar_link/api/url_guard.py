"""Outbound URL allow-listing + response byte cap for the LitVar2 client (F-07).

The client keeps httpx's redirect machinery (``follow_redirects=True``) but
validates *every* hop with an httpx **request** event-hook and caps the response
body with a **response** event-hook. Keeping httpx's 301/302/303->GET vs 307/308
method semantics (rather than a hand-rolled manual loop) avoids silent
correctness bugs; we only *validate* each outgoing request.

Guard rules (per hop, incl. auto-followed redirects):
- scheme MUST be ``https`` (no plaintext downgrade),
- no ``user:pass@`` userinfo (no smuggled credentials),
- host MUST be in the EXACT allowlist (no suffix/substring match),
- method MUST be ``GET`` (the LitVar2 client is read-only / GET-only).

The allowlist is DERIVED from the configured base URL origin(s) at client-build
time -- never hardcoded -- so an operator base-URL override stays enforced.

Both guard exceptions subclass :class:`LitVarAPIError` so the client's retry loop
treats them as **fail-fast / non-retryable** (they must not look like a transient
transport error and be retried).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from litvar_link.exceptions import LitVarAPIError

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    import httpx

_ALLOWED_METHODS = frozenset({"GET"})


class DisallowedURLError(LitVarAPIError):
    """An outbound request/redirect targeted a non-allowlisted URL. NON-RETRYABLE.

    HOST-FREE MESSAGE: the caller/attacker-controlled offending value (redirect
    host, scheme, or method) is NEVER interpolated into the exception
    ``message`` -- a host in the message reaches the logs via chained-exception
    rendering (``raise ... from e`` + ``logger.exception``) or ANY ``str(exc)``
    surface (e.g. the REST ``_api_error_handler``). The offending value is kept
    No attacker-controlled destination detail is retained on the exception.
    """

    def __init__(self, *_: object, **__: object) -> None:
        super().__init__("outbound URL rejected")


class ResponseTooLargeError(LitVarAPIError):
    """A response body exceeded the configured byte cap. NON-RETRYABLE."""

    def __init__(self, *_: object, **__: object) -> None:
        super().__init__("outbound response rejected")


@dataclass(frozen=True)
class AllowedOrigin:
    """Normalized HTTPS origin that an outbound request may target."""

    host: str
    port: int


def build_allowed_origins(*base_urls: str) -> frozenset[AllowedOrigin]:
    """Return normalized configured origins extracted from ``base_urls``.

    Hostless / unparseable inputs are ignored so a misconfigured extra never
    silently widens the allowlist.
    """
    origins: set[AllowedOrigin] = set()
    for url in base_urls:
        parsed = urlsplit(url)
        host = parsed.hostname
        if host:
            origins.add(AllowedOrigin(host.lower(), parsed.port or 443))
    return frozenset(origins)


def build_host_allowlist(*base_urls: str) -> frozenset[str]:
    """Compatibility helper for callers that only need configured host names."""
    return frozenset(origin.host for origin in build_allowed_origins(*base_urls))


def make_url_guard(
    allowed_origins: frozenset[AllowedOrigin] | frozenset[str],
) -> Callable[[httpx.Request], Awaitable[None]]:
    """Build an httpx request event-hook validating each outgoing request/hop."""

    normalized_origins = frozenset(
        AllowedOrigin(origin, 443) if isinstance(origin, str) else origin
        for origin in allowed_origins
    )

    async def _guard(request: httpx.Request) -> None:
        # Every message is fixed and host/scheme/method-free.
        method = request.method.upper()
        if method not in _ALLOWED_METHODS:
            raise DisallowedURLError()
        url = request.url
        if url.scheme != "https":
            raise DisallowedURLError()
        # Reject ANY userinfo, incl. empty-username/password forms. Checking only
        # ``url.username or url.password`` MISSES a userinfo whose creds both parse
        # empty (e.g. ``https://:@host/`` -> both decode to ``''`` but the raw
        # ``userinfo`` is ``b':'``): a smuggled-credential authority on an
        # otherwise-allowlisted host would slip through. Inspect the raw
        # ``userinfo`` bytes so any ``@``-before-host authority is rejected.
        authority = str(url).split("://", 1)[-1].split("/", 1)[0]
        if url.userinfo or "@" in authority:
            raise DisallowedURLError()
        host = (url.host or "").lower()
        origin = AllowedOrigin(host, url.port or 443)
        if origin not in normalized_origins:
            raise DisallowedURLError()

    return _guard


def make_response_cap(
    max_bytes: int,
) -> Callable[[httpx.Response], Awaitable[None]]:
    """Build an httpx response event-hook enforcing a fail-closed byte cap.

    ``Content-Length`` is a cheap first guard (a declared length above the cap
    fails immediately); it is never trusted alone (chunked/gzip bodies), so the
    body is streamed and aborted the moment the running total exceeds the cap --
    the buffered bytes are then materialized onto the response so the normal
    ``.text`` / ``.json()`` reads keep working.
    """

    async def _cap(response: httpx.Response) -> None:
        declared = response.headers.get("Content-Length")
        if declared is not None:
            try:
                if int(declared) > max_bytes:
                    raise ResponseTooLargeError()
            except ValueError:
                pass  # malformed header -> fall through to streamed enforcement
        total = 0
        chunks: list[bytes] = []
        async for chunk in response.aiter_bytes():
            total += len(chunk)
            if total > max_bytes:
                raise ResponseTooLargeError()
            chunks.append(chunk)
        # Materialize the capped body so the normal buffered .text/.json() reads
        # keep working after we consumed the stream to enforce the cap.
        response._content = b"".join(chunks)

    return _cap
