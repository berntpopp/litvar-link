"""MCP tool boundary: the ratified GeneFoundry Response-Envelope Standard v1.

Every LitVar-Link tool body runs through :func:`run_tool`, which:

- On success, banner-wraps the body's returned dict:
  ``{"success": True, <payload>, "_meta": {...}}`` (:func:`envelope.success_envelope`).
- On failure, NEVER lets the exception propagate as a raised
  ``fastmcp.exceptions.ToolError``. Instead it classifies the exception into
  the closed ``error_code`` enum and RETURNS a flat, in-band error frame
  (:func:`envelope.error_envelope`) wrapped in a :class:`fastmcp.tools.tool.ToolResult`
  with ``is_error=True`` -- verified against the installed fastmcp 3.4.2 API:
  ``ToolResult.__init__`` accepts ``structured_content`` + ``is_error``, and
  ``Tool.convert_result`` passes a returned ``ToolResult`` straight through, so
  this both puts the flat envelope in ``structuredContent`` AND sets the wire
  ``CallToolResult.isError`` so MCP clients surface the failure to the model.

``ToolValidationError`` remains the tool-body-facing signal for user-recoverable
input problems (empty query, malformed RSID/gene) -- tool bodies still ``raise``
it internally to short-circuit, exactly as before. What changed is what
``run_tool`` does with it: it now classifies and returns the flat envelope
instead of re-raising.
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from fastmcp.tools.tool import ToolResult

from litvar_link.exceptions import (
    LitVarAPIError,
    RateLimitError,
    ServiceUnavailableError,
)
from litvar_link.exceptions import ValidationError as LitVarValidationError
from litvar_link.mcp.envelope import ErrorCode, error_envelope, success_envelope
from litvar_link.mcp.untrusted_content import FORBIDDEN_CODEPOINTS, UntrustedTextLimitError

logger = logging.getLogger(__name__)

_HTTP_NOT_FOUND = 404
_HTTP_CLIENT_ERROR = 400
_MAX_MESSAGE_CHARS = 240

# Fixed, upstream-body-free messages for errors whose exception text embeds the
# raw (caller/attacker-influenceable) LitVar2 response body. The actionable
# guidance travels separately in ``recovery_action``.
_SAFE_UPSTREAM_MESSAGE: dict[ErrorCode, str] = {
    "not_found": "LitVar2 has no record for the requested identifier.",
    "invalid_input": "LitVar2 rejected the request as invalid.",
    "upstream_unavailable": "The LitVar2 upstream returned an error or is unavailable.",
}


class ToolValidationError(Exception):
    """Visible, user-recoverable validation failure (maps to ``invalid_input``)."""


def _classify_api_error(exc: LitVarAPIError) -> tuple[ErrorCode, bool, str]:
    """Classify a (non-rate-limit, non-unavailable) ``LitVarAPIError`` by status."""
    status = exc.status_code
    if status == _HTTP_NOT_FOUND:
        return (
            "not_found",
            False,
            "Confirm the identifier; call search_genetic_variants or resolve_rsid "
            "to resolve free text into a valid id first.",
        )
    if status is not None and status >= _HTTP_CLIENT_ERROR:
        return (
            "invalid_input",
            False,
            "Fix the offending argument per the message and retry with corrected input.",
        )
    return (
        "upstream_unavailable",
        True,
        "Retry after a short backoff; call get_server_capabilities if it persists.",
    )


def _classify(exc: Exception) -> tuple[ErrorCode, bool, str]:
    """Return ``(error_code, retryable, recovery_action)`` for a caught exception.

    Subclass ordering matters: ``RateLimitError`` and ``ServiceUnavailableError``
    both subclass ``LitVarAPIError``, so they MUST be checked first or they fall
    through to the generic (status-code-driven) ``LitVarAPIError`` branch.
    """
    if isinstance(exc, ToolValidationError | LitVarValidationError):
        return (
            "invalid_input",
            False,
            "Fix the offending argument per the message and retry with corrected input.",
        )
    if isinstance(exc, UntrustedTextLimitError):
        return (
            "response_limit_exceeded",
            False,
            "The response exceeded a Response-Envelope v1.1 untrusted-content "
            "ceiling (object count or byte size). Lower `limit` and retry.",
        )
    if isinstance(exc, RateLimitError):
        return (
            "rate_limited",
            True,
            "Back off (exponentially) and retry the same call; reduce request concurrency.",
        )
    if isinstance(exc, ServiceUnavailableError):
        return (
            "upstream_unavailable",
            True,
            "Retry after a short backoff; call get_server_capabilities if it persists.",
        )
    if isinstance(exc, LitVarAPIError):
        return _classify_api_error(exc)
    if isinstance(exc, TimeoutError):
        return (
            "upstream_unavailable",
            True,
            "Retry after a short backoff; the upstream request timed out.",
        )
    return (
        "internal",
        False,
        "Retry later; if it persists, call get_server_capabilities for server health context.",
    )


def _sanitize_message(text: str) -> str:
    """Strip forbidden control/zero-width/bidi code points and length-cap.

    Applied to every caller-visible message so a hostile upstream or input can
    never smuggle bidi-override or zero-width characters into the error frame
    (the same code-point set the untrusted-text fence removes).
    """
    clean = "".join(char for char in text if ord(char) not in FORBIDDEN_CODEPOINTS)
    return clean[:_MAX_MESSAGE_CHARS]


def _carries_upstream_body(exc: Exception) -> bool:
    """True when the exception's text embeds the raw LitVar2 response body.

    Only the base ``LitVarAPIError`` (raised by ``raise_for_status_code`` with a
    preview of the upstream 4xx body) carries attacker-influenceable upstream
    prose. Its ``ValidationError`` / ``RateLimitError`` / ``ServiceUnavailableError``
    subclasses are constructed with our own fixed strings, so their (safe)
    messages are surfaced verbatim (sanitized).
    """
    return isinstance(exc, LitVarAPIError) and not isinstance(
        exc, LitVarValidationError | RateLimitError | ServiceUnavailableError
    )


def _safe_message(exc: Exception, *, error_code: ErrorCode, tool_name: str, request_id: str) -> str:
    """Return a message safe to surface to LLM callers.

    - ``internal`` errors are fully opaque (tool name + request id only).
    - Errors whose exception text embeds the raw upstream response body
      (base ``LitVarAPIError``) NEVER echo that body -- a caller-controlled query
      can make LitVar2 reflect hostile prose (incl. control/zero-width/bidi)
      into a 4xx body. A fixed, upstream-body-free message is returned instead;
      the raw body is deliberately NOT logged either, to preserve the M3
      no-PII-in-logs invariant.
    - Our own validation/rate-limit/timeout messages are developer-authored (no
      secrets, no upstream body) and are surfaced verbatim, but still sanitized
      of forbidden code points defensively.
    """
    if error_code == "internal":
        return (
            f"Internal error in {tool_name} (request_id={request_id}). "
            "Retry later or call get_server_capabilities."
        )
    if _carries_upstream_body(exc):
        return _SAFE_UPSTREAM_MESSAGE.get(error_code, "LitVar2 upstream returned an error.")
    text = str(exc) or exc.__class__.__name__
    return _sanitize_message(text)


async def run_tool(
    tool_name: str,
    body: Callable[[], Awaitable[dict[str, Any]]],
) -> dict[str, Any] | ToolResult:
    """Execute a tool body and return the Response-Envelope Standard v1 frame.

    Success: the body's dict, banner-wrapped (``success``/``_meta`` injected).
    Failure: the body's exception is classified and RETURNED (never raised) as
    a flat error frame, wrapped in a ``ToolResult(is_error=True)`` so the wire
    ``isError`` flag reaches the client per Rules §2.
    """
    request_id = uuid.uuid4().hex[:12]
    start = time.perf_counter()
    try:
        result = await body()
    except Exception as exc:  # error boundary: catch-all is intentional
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        error_code, retryable, recovery_action = _classify(exc)
        message = _safe_message(
            exc, error_code=error_code, tool_name=tool_name, request_id=request_id
        )
        logger.warning(
            "mcp_tool_error tool=%s request_id=%s error_code=%s exc=%s",
            tool_name,
            request_id,
            error_code,
            exc.__class__.__name__,
        )
        payload = error_envelope(
            tool_name=tool_name,
            request_id=request_id,
            elapsed_ms=elapsed_ms,
            error_code=error_code,
            message=message,
            retryable=retryable,
            recovery_action=recovery_action,
        )
        return ToolResult(structured_content=payload, is_error=True)

    elapsed_ms = int((time.perf_counter() - start) * 1000)
    return success_envelope(
        result,
        tool_name=tool_name,
        request_id=request_id,
        elapsed_ms=elapsed_ms,
    )
