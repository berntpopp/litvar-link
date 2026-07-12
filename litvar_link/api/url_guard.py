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

The allowlist is DERIVED from the configured base URL host(s) at client-build
time -- never hardcoded -- so an operator base-URL override stays enforced.

Both guard exceptions subclass :class:`LitVarAPIError` so the client's retry loop
treats them as **fail-fast / non-retryable** (they must not look like a transient
transport error and be retried).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from litvar_link.exceptions import LitVarAPIError

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    import httpx

_ALLOWED_METHODS = frozenset({"GET"})


class DisallowedURLError(LitVarAPIError):
    """An outbound request/redirect targeted a non-allowlisted URL. NON-RETRYABLE."""


class ResponseTooLargeError(LitVarAPIError):
    """A response body exceeded the configured byte cap. NON-RETRYABLE."""


def build_host_allowlist(*base_urls: str) -> frozenset[str]:
    """Return the lowercased set of hosts extracted from ``base_urls``.

    Hostless / unparseable inputs are ignored so a misconfigured extra never
    silently widens the allowlist.
    """
    hosts: set[str] = set()
    for url in base_urls:
        host = urlsplit(url).hostname
        if host:
            hosts.add(host.lower())
    return frozenset(hosts)


def make_url_guard(
    allowed_hosts: frozenset[str],
) -> Callable[[httpx.Request], Awaitable[None]]:
    """Build an httpx request event-hook validating each outgoing request/hop."""

    async def _guard(request: httpx.Request) -> None:
        if request.method.upper() not in _ALLOWED_METHODS:
            raise DisallowedURLError(f"method not permitted: {request.method}")
        url = request.url
        if url.scheme != "https":
            raise DisallowedURLError(f"non-https scheme not permitted: {url.scheme}")
        if url.username or url.password:
            raise DisallowedURLError("userinfo in URL not permitted")
        host = (url.host or "").lower()
        if host not in allowed_hosts:
            raise DisallowedURLError(f"host not allowlisted: {host}")

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
                    raise ResponseTooLargeError(
                        f"declared Content-Length {declared} exceeds cap {max_bytes}",
                    )
            except ValueError:
                pass  # malformed header -> fall through to streamed enforcement
        total = 0
        chunks: list[bytes] = []
        async for chunk in response.aiter_bytes():
            total += len(chunk)
            if total > max_bytes:
                raise ResponseTooLargeError(f"response body exceeded cap {max_bytes} bytes")
            chunks.append(chunk)
        # Materialize the capped body so the normal buffered .text/.json() reads
        # keep working after we consumed the stream to enforce the cap.
        response._content = b"".join(chunks)

    return _cap
