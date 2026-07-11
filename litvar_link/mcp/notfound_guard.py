"""FastMCP-core not-found reflection guard (Response-Envelope v1.1 fast-follow).

FastMCP core (pinned ``>=3.4.4,<4.0.0``) and the MCP SDK reflect the caller's OWN
requested tool name / resource URI / prompt name back to the caller (and to logs)
BEFORE any backend middleware runs. This module closes that residual with fixed,
input-free messages built from CONSTANTS only, mirroring the ratified fleet
references (``mondo``/``hpo`` registry preflight, ``clinvar`` protocol backstop,
``panelapp``/``hpo`` validation-log scrub filter).

The reflected text is *caller-supplied* (a caller self-reflection surface), so
this is materially lower-risk than the upstream-injection leak the prior sweep
closed. It is still worth closing: the reflected name/URI -- with any
control/zero-width/bidi/NUL code points -- lands in shared operator logs and in an
agent's tool-result context. Fixed constants remove the channel entirely.

Layers (spec §3), copied per repo (no shared runtime library exists fleet-wide):

* Layer 1 -- ``on_call_tool`` registry preflight: ``get_tool(name)`` returns
  ``None`` for an unknown/disabled tool, so we return a fixed, name-free
  ``not_found`` envelope BEFORE core dispatch. Closes the unknown-TOOL surface;
  never echoes ``_meta.tool``.
* Layer 2 -- ``on_read_resource`` boundary: an unknown (URL-valid) resource makes
  core raise ``NotFoundError("Unknown resource: '<uri>'")``; we re-raise a fixed
  URI-free ``ResourceError``. LitVar-Link registers no resources, so every read is
  a not-found -- there are no author-authored ResourceError messages to preserve.
* Layer 3 -- protocol-handler backstop: wraps the raw ``CallTool`` / ``ReadResource``
  / ``GetPrompt`` request handlers as the OUTERMOST layer. Replaces any non-envelope
  ``isError`` tool result (the unknown-tool *return* path) and re-raises fixed
  input-free messages for resource/prompt dispatch failures -- the ONLY layer that
  covers the unknown-PROMPT surface (FastMCP core echoes ``Unknown prompt: '<name>'``
  to the caller even when no prompts are registered).
* Layer 5 -- validation-log scrub filter: FastMCP's pre-middleware, the MCP SDK
  session's request-validation logs, AND FastMCP's ``AggregateProvider`` echo the
  raw name/URI (with code points) on their own loggers/handlers at ANY level
  (``Tool cache miss for <name>``, ``Handler called: ... <name/uri>``, ``Failed to
  validate request: <uri>``, and -- on a provider fault during a get_tool/
  get_resource/get_prompt lookup -- ``Error during get_tool('<name>') from
  provider ...: <exc>`` whose ``operation`` embeds the requested name/URI verbatim
  and whose ``<exc>`` may repeat it). The filter neutralizes those records at the
  source logger (and its non-propagating Rich handlers) so caller input never
  reaches a log sink.

Layer 4 (arg/params validation) is ``FastMCP(mask_error_details=True)`` on the
facade (already present). Layer 6 (OTel span redaction) is a no-op here: FastMCP
pulls in ``opentelemetry-api`` transitively, but ``opentelemetry-sdk`` is absent,
so the tracer provider is non-recording -- no span exception attributes are ever
captured, so there is nothing to redact (fleet policy: do NOT add the SDK dep).
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, cast

import mcp.types
from fastmcp import FastMCP
from fastmcp.exceptions import NotFoundError as FastMCPNotFoundError
from fastmcp.exceptions import ResourceError
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from fastmcp.tools.tool import ToolResult

from litvar_link.mcp.envelope import error_envelope

logger = logging.getLogger(__name__)

# Fixed, input-free public messages. They NEVER contain the requested name/URI
# (nor a ``_meta.tool`` echo of it): sanitation strips code points but not
# injection prose, so a fixed constant is the only safe source (prior-sweep
# lesson). ``not_found`` reuses this repo's closed error-code enum (envelope.py).
_UNKNOWN_TOOL_MESSAGE = "The requested tool is not available."
_UNKNOWN_RESOURCE_MESSAGE = "The requested resource is not available."
_UNKNOWN_PROMPT_MESSAGE = "The requested prompt is not available."
_UNKNOWN_TOOL_RECOVERY = "Call get_server_capabilities to list the available tools, then retry."


def unknown_tool_envelope() -> dict[str, Any]:
    """Build the fixed, name-free ``not_found`` error envelope for an unknown tool.

    ``tool_name=None`` keeps ``_meta.tool`` from reflecting the caller-controlled
    (untrusted) requested name. ``request_id`` is a fresh id for traceability;
    ``elapsed_ms=0`` because no tool body ran.
    """
    return error_envelope(
        tool_name=None,
        request_id=uuid.uuid4().hex[:12],
        elapsed_ms=0,
        error_code="not_found",
        message=_UNKNOWN_TOOL_MESSAGE,
        retryable=False,
        recovery_action=_UNKNOWN_TOOL_RECOVERY,
    )


def unknown_tool_result() -> ToolResult:
    """A ``ToolResult`` carrying the fixed unknown-tool envelope.

    ``is_error=True`` maps to ``CallToolResult.isError`` on the wire (ratified
    fleet contract: an ``is_error=False`` structured result would be validated by
    the FastMCP Client against a tool output schema, and a hostile requested name
    logged on the client logger on failure). The TextContent mirror is auto-derived
    from ``structured_content`` (both are fixed constants, so neither can leak).
    """
    return ToolResult(structured_content=unknown_tool_envelope(), is_error=True)


class NotFoundGuard(Middleware):
    """Layer 1 (tool preflight) + Layer 2 (resource boundary)."""

    async def on_call_tool(
        self,
        context: MiddlewareContext[Any],
        call_next: CallNext[Any, ToolResult],
    ) -> ToolResult:
        """Preflight the tool NAME; an unknown name never reaches core dispatch.

        ``get_tool`` returns ``None`` (it does not raise) for an unknown or
        disabled tool, so an unknown name is caught here and answered with a
        fixed, name-free envelope. Otherwise defer to the tool body.
        """
        fctx = getattr(context, "fastmcp_context", None)
        name = getattr(getattr(context, "message", None), "name", None)
        if fctx is not None and isinstance(name, str):
            try:
                tool = await fctx.fastmcp.get_tool(name)
            except Exception:
                tool = object()  # resolution failure: defer to core, do not mask
            if tool is None:
                logger.warning("mcp_unknown_tool")
                return unknown_tool_result()
        return await call_next(context)

    async def on_read_resource(
        self,
        context: MiddlewareContext[Any],
        call_next: CallNext[Any, Any],
    ) -> Any:
        """Emit a FIXED, URI-free error for a resource not-found / read failure.

        The requested URI is caller-controlled; FastMCP core echoes it
        (``Unknown resource: '<uri>'`` / ``Error reading resource '<uri>'``) in
        both the direct exception and the protocol error. Re-raise a fixed message
        so the URI never reaches the caller/protocol. Log the exception CLASS only.
        """
        try:
            return await call_next(context)
        except FastMCPNotFoundError:
            logger.warning("mcp_resource_not_found")
            raise ResourceError(_UNKNOWN_RESOURCE_MESSAGE) from None
        except Exception as exc:
            logger.warning("mcp_resource_error error_type=%s", type(exc).__name__)
            raise ResourceError(_UNKNOWN_RESOURCE_MESSAGE) from None


# ---------------------------------------------------------------------------
# Layer 3 -- protocol-handler backstop (clinvar/hpo pattern)
# ---------------------------------------------------------------------------


class ProtocolError(Exception):
    """A dispatch-level failure re-raised with a FIXED, input-free message."""


def _is_structured_envelope(call_result: mcp.types.CallToolResult) -> bool:
    """True if an ``isError`` result carries one of OUR JSON envelopes.

    Distinguishes a structured litvar-link error (already input-free -- it has an
    ``error_code``) from a RAW FastMCP dispatch error whose plain-text message
    echoes the caller-supplied tool name (``Unknown tool: '<name>'``).
    """
    if not call_result.content:
        return False
    text = getattr(call_result.content[0], "text", None)
    if not isinstance(text, str):
        return False
    try:
        obj = json.loads(text)
    except (ValueError, TypeError):
        return False
    return isinstance(obj, dict) and "error_code" in obj


def _fixed_tool_not_found_result() -> mcp.types.ServerResult:
    """A fixed, input-free ServerResult for an unknown/failed tool dispatch."""
    envelope = unknown_tool_envelope()
    return mcp.types.ServerResult(
        mcp.types.CallToolResult(
            content=[mcp.types.TextContent(type="text", text=json.dumps(envelope))],
            structuredContent=envelope,
            isError=True,
        )
    )


def _wrap_call_tool_handler(handlers: dict[Any, Any]) -> None:
    """Replace the raw CallTool handler's name-echoing ``isError`` return path."""
    call_tool = handlers.get(mcp.types.CallToolRequest)
    if call_tool is None:
        return

    async def wrapped_call_tool(
        request: mcp.types.CallToolRequest,
        *,
        _orig: Any = call_tool,
    ) -> mcp.types.ServerResult:
        try:
            result = cast(mcp.types.ServerResult, await _orig(request))
        except FastMCPNotFoundError:
            # Unknown-tool *raise* drift (should not reach here once Layer 1
            # is active) -- answer with the fixed name-free envelope.
            logger.warning("mcp_protocol_error kind=tool")
            return _fixed_tool_not_found_result()
        # FastMCP *returns* an isError CallToolResult with a raw plain-text
        # message ("Unknown tool: '<name>'") for an unknown tool; replace any
        # isError result that is NOT one of our structured envelopes. A masked
        # runtime ToolError is a FastMCPError (raised, not returned) and does
        # not pass through here, so this only catches the name-echoing return.
        root = getattr(result, "root", None)
        if (
            isinstance(root, mcp.types.CallToolResult)
            and root.isError
            and not _is_structured_envelope(root)
        ):
            logger.warning("mcp_protocol_error kind=tool")
            return _fixed_tool_not_found_result()
        return result

    handlers[mcp.types.CallToolRequest] = wrapped_call_tool


def _wrap_component_handler(
    handlers: dict[Any, Any], request_type: Any, message: str, kind: str
) -> None:
    """Re-raise a fixed, input-free message for a resource/prompt dispatch failure."""
    orig = handlers.get(request_type)
    if orig is None:
        return

    async def wrapped(
        request: Any,
        *,
        _orig: Any = orig,
        _message: str = message,
        _kind: str = kind,
    ) -> Any:
        try:
            return await _orig(request)
        except Exception as exc:
            # Re-raise with a FIXED, input-free message so no requested name/URI
            # (or its code points) reaches the JSON-RPC error frame. Log the
            # exception CLASS only (never the caller-controlled value).
            logger.warning("mcp_protocol_error kind=%s type=%s", _kind, type(exc).__name__)
            raise ProtocolError(_message) from None

    handlers[request_type] = wrapped


def install_protocol_error_handler(mcp_server: FastMCP) -> None:
    """Wrap the tool/resource/prompt request handlers as the OUTERMOST layer.

    A FastMCP core not-found (or read) error can no longer reflect the
    caller-supplied name/URI. Install AFTER all tools/resources/prompts are
    registered so the handlers exist. (Parameter is ``mcp_server`` -- not ``mcp``
    -- so it never shadows the ``import mcp.types`` module used below.)
    """
    handlers = mcp_server._mcp_server.request_handlers
    _wrap_call_tool_handler(handlers)
    _wrap_component_handler(
        handlers, mcp.types.ReadResourceRequest, _UNKNOWN_RESOURCE_MESSAGE, "resource"
    )
    _wrap_component_handler(handlers, mcp.types.GetPromptRequest, _UNKNOWN_PROMPT_MESSAGE, "prompt")


# ---------------------------------------------------------------------------
# Layer 5 -- validation-log scrub filter (panelapp/hpo pattern)
# ---------------------------------------------------------------------------
#
# FastMCP core and the MCP SDK log the caller's OWN requested name/URI (with any
# control/zero-width/bidi/NUL code points) on their OWN loggers, BEFORE this
# module's guard reshapes the caller-facing frame. ``mask_error_details=True``
# masks the tool *response*, not these *log* records. Each marker below is a
# substring of ``record.msg`` (the %-template or an already-interpolated f-string)
# of a real record on this FastMCP/mcp version; matching on ``msg`` covers both
# forms because the scrub replaces the message AND clears ``args``.
_REFLECTION_MARKERS: tuple[str, ...] = (
    "Handler called: call_tool",
    "Handler called: read_resource",
    "Handler called: get_prompt",
    "Tool cache miss for",
    "Invalid arguments for tool",
    "Error calling tool",
    "Error reading resource",
    "Failed to validate request",
    "Failed to validate notification",
    "Message that failed validation",
    # AggregateProvider (fastmcp.server.providers.aggregate) logs a WARNING with
    # the message ALREADY formatted via an f-string: the ``operation`` embeds the
    # caller-requested name/URI verbatim (``get_tool('<name>')`` /
    # ``get_resource('<uri>')`` / ``get_prompt('<name>')``) and ``{result}`` is
    # ``str(exc)`` of a provider fault (which may echo the same name/URI + code
    # points). The leak is in ``record.msg`` (not ``args``), so the marker branch
    # -- which replaces the WHOLE msg -- is what closes it; clearing args alone
    # would not. ``Duplicate`` covers the sibling collision warning (``{key!r}``).
    "Error during ",
    "Duplicate ",
)
_SCRUBBED_MESSAGE = "MCP request detail omitted (caller input redacted)."

#: Framework logger-name prefixes for the WARNING+ args-clearing fallback.
_FRAMEWORK_PREFIXES = ("fastmcp", "mcp")

#: The SOURCE loggers on which the reflecting records are CREATED. A logging
#: filter runs only for records emitted on the logger it is attached to (ancestor
#: filters are SKIPPED during propagation), so attach directly to each originating
#: logger. Root covers ``mcp.shared.session``'s bare module-level ``logging.warning``
#: / ``logging.debug`` (verified: mcp/shared/session.py). ``fastmcp`` / ``mcp`` are
#: their non-propagating Rich-handler parents (a root-only filter would miss them).
_SOURCE_LOGGERS: tuple[str, ...] = (
    "",  # root -- mcp.shared.session request-validation failures
    "fastmcp",
    "fastmcp.server.server",
    "fastmcp.server.mixins.mcp_operations",
    "fastmcp.server.providers.aggregate",  # provider-fault warning echoes name/URI
    "mcp",
    "mcp.server.lowlevel.server",
)


class ExternalErrorDetailFilter(logging.Filter):
    """Scrub caller-supplied name/URI from FastMCP/MCP framework log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Neutralize reflecting records in place; always emit the scrubbed record."""
        msg = record.msg if isinstance(record.msg, str) else ""
        # Records that reflect the caller-supplied name/URI (any logger, any
        # level): replace the whole message and clear the interpolated args and
        # any traceback so no caller input reaches a log sink.
        if any(marker in msg for marker in _REFLECTION_MARKERS):
            record.msg = _SCRUBBED_MESSAGE
            record.args = ()
            record.exc_info = None
            record.exc_text = None
            record.stack_info = None
            return True
        # Fallback: other FastMCP/MCP framework WARNING+ records may carry
        # caller-derived detail in their interpolated args -- drop it.
        if record.levelno < logging.WARNING:
            return True
        if not record.name.startswith(_FRAMEWORK_PREFIXES):
            return True
        record.args = ()
        record.exc_info = None
        record.exc_text = None
        return True


#: One shared filter instance so idempotent installs don't stack duplicates.
_SHARED_FILTER = ExternalErrorDetailFilter()


def _has_filter(target: logging.Logger | logging.Handler) -> bool:
    return any(isinstance(existing, ExternalErrorDetailFilter) for existing in target.filters)


def install_validation_log_filter() -> None:
    """Attach the scrub filter to every SOURCE logger (and its handlers), idempotently.

    Attach directly to each originating logger -- including ROOT (where
    ``mcp.shared.session`` emits via bare ``logging.warning``/``logging.debug``) and
    FastMCP's own ``fastmcp`` logger, whose non-propagating ``RichHandler``s would
    otherwise bypass a root-only filter. Also attach to each logger's existing
    handlers as belt-and-braces. Call after the FastMCP facade is built so the
    framework handlers already exist.
    """
    for name in _SOURCE_LOGGERS:
        target = logging.getLogger(name)
        if not _has_filter(target):
            target.addFilter(_SHARED_FILTER)
        for handler in target.handlers:
            if not _has_filter(handler):
                handler.addFilter(_SHARED_FILTER)
