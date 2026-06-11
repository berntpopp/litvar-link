"""MCP error contract: visible recoverable errors vs masked internal errors.

- ``ToolValidationError`` is a *user-recoverable* error (empty query, bad limit,
  malformed RSID/gene). It is surfaced verbatim so the agent can self-correct.
- Any other exception is an *internal* error. Its detail is masked
  (``mask_error_details=True`` on the FastMCP server) and re-raised as a generic
  ``ToolInternalError`` carrying only the tool name + a correlation id.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)


class ToolValidationError(ValueError):
    """Visible, user-recoverable validation failure (safe to show the agent)."""


class ToolInternalError(RuntimeError):
    """Masked internal failure; carries no upstream detail."""


async def run_tool[T](tool_name: str, body: Callable[[], Awaitable[T]]) -> T:
    """Execute a tool body, letting validation errors through and masking the rest.

    ``ToolValidationError`` propagates unchanged (the agent sees the message).
    Everything else is logged with a correlation id and re-raised as a generic
    ``ToolInternalError`` so no internal detail leaks to the client.
    """
    try:
        return await body()
    except ToolValidationError:
        raise
    except Exception as exc:  # error boundary: catch-all is intentional
        correlation_id = uuid.uuid4().hex[:12]
        logger.warning(
            "mcp_tool_internal_error tool=%s correlation_id=%s exc=%s",
            tool_name,
            correlation_id,
            exc.__class__.__name__,
        )
        msg = (
            f"Internal error in {tool_name} "
            f"(correlation_id={correlation_id}). Retry later or call "
            f"get_server_capabilities."
        )
        raise ToolInternalError(msg) from None
