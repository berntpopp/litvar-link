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

logger = logging.getLogger(__name__)

_HTTP_NOT_FOUND = 404
_HTTP_CLIENT_ERROR = 400
_MAX_MESSAGE_CHARS = 240


class ToolValidationError(Exception):
    """Visible, user-recoverable validation failure (maps to ``invalid_input``)."""


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


def _safe_message(exc: Exception, *, error_code: ErrorCode, tool_name: str, request_id: str) -> str:
    """Return a message safe to surface to LLM callers.

    Validation/upstream errors carry developer- or LitVar2-authored text (no
    secrets), so it is surfaced verbatim (length-capped). Internal errors are
    fully opaque -- only the tool name + a request id, never exception detail --
    matching the prior masking behavior.
    """
    if error_code == "internal":
        return (
            f"Internal error in {tool_name} (request_id={request_id}). "
            "Retry later or call get_server_capabilities."
        )
    text = str(exc) or exc.__class__.__name__
    return text[:_MAX_MESSAGE_CHARS]


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
