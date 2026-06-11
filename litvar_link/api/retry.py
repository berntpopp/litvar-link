"""Retry/backoff policy and HTTP status classification for the LitVar2 client."""

from __future__ import annotations

from litvar_link.exceptions import (
    LitVarAPIError,
    RateLimitError,
    ServiceUnavailableError,
)

HTTP_TOO_MANY_REQUESTS = 429
HTTP_SERVER_ERROR = 500
HTTP_CLIENT_ERROR = 400
_ERROR_TEXT_PREVIEW = 200


def backoff_delay(*, base: float, attempt: int) -> float:
    """Exponential backoff: ``base * 2**attempt`` seconds."""
    return float(base * (2**attempt))


def raise_for_status_code(
    status_code: int,
    *,
    url: str,
    text: str,
    retry_after: float | None = None,
) -> None:
    """Raise the appropriate LitVar error for a non-2xx status, else return None.

    429 -> RateLimitError, 5xx -> ServiceUnavailableError, other 4xx ->
    LitVarAPIError.
    """
    if status_code == HTTP_TOO_MANY_REQUESTS:
        msg = f"Rate limit exceeded for {url}"
        raise RateLimitError(msg, retry_after=retry_after if retry_after else 60.0)
    if status_code >= HTTP_SERVER_ERROR:
        msg = f"LitVar2 service error: HTTP {status_code}"
        raise ServiceUnavailableError(msg)
    if status_code >= HTTP_CLIENT_ERROR:
        error_text = text[:_ERROR_TEXT_PREVIEW] if text else "Unknown error"
        msg = f"HTTP {status_code}: {error_text}"
        raise LitVarAPIError(msg, status_code=status_code)
    return None
