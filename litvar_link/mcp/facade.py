"""Hand-authored FastMCP facade for LitVar-Link."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastmcp import FastMCP

from litvar_link import __version__
from litvar_link.mcp.capabilities import INSTRUCTIONS
from litvar_link.mcp.tools import register_all


def create_litvar_mcp(*, service_factory: Callable[[], Any]) -> FastMCP:
    """Build the LitVar-Link MCP server.

    ``service_factory`` is a lazy callable so HTTP mode can defer to a per-request
    ``VariantService`` and stdio mode can hold a directly constructed instance.
    """
    mcp: FastMCP = FastMCP(
        name="litvar-link",
        version=__version__,
        instructions=INSTRUCTIONS,
        mask_error_details=True,
        # Tool-Surface Budget v1 B4: the constructor defaults this to True and
        # appends DereferenceRefsMiddleware, which inlines every $defs/$ref at
        # every use site. Free to disable, and safe: 0 of our INPUT schemas
        # contain a $ref, so no schema-driven client can be affected.
        dereference_schemas=False,
    )

    # Guard the FastMCP-core not-found reflection surface: core echoes the
    # caller's OWN requested tool name / resource URI / prompt name (with any
    # control/zero-width/bidi/NUL code points) to the caller and to logs BEFORE
    # backend middleware runs. NotFoundGuard preflights the tool NAME (unknown ->
    # fixed name-free envelope) and fixes the on_read_resource boundary; it is
    # added FIRST so it is the OUTERMOST middleware. See notfound_guard.py.
    from litvar_link.mcp.notfound_guard import (
        NotFoundGuard,
        install_protocol_error_handler,
        install_validation_log_filter,
    )

    mcp.add_middleware(NotFoundGuard())

    # Layer 5: scrub FastMCP-core / MCP-SDK validation logs that would echo the
    # caller-supplied name/URI at ANY level (idempotent; process-global).
    install_validation_log_filter()

    register_all(mcp, service_factory=service_factory)

    # Layer 3: install the protocol-handler backstop AFTER every tool/resource/
    # prompt is registered (so the request handlers exist). Outermost wrapper on
    # the raw CallTool/ReadResource/GetPrompt handlers -- catches the unknown-tool
    # *return* path and any resource/prompt dispatch error that would echo the
    # requested name/URI (the only layer covering the unknown-prompt surface).
    install_protocol_error_handler(mcp)
    return mcp
