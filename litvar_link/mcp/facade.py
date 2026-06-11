"""Hand-authored FastMCP facade for LitVar-Link."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastmcp import FastMCP

from litvar_link.mcp.capabilities import INSTRUCTIONS
from litvar_link.mcp.tools import register_all


def create_litvar_mcp(*, service_factory: Callable[[], Any]) -> FastMCP:
    """Build the LitVar-Link MCP server.

    ``service_factory`` is a lazy callable so HTTP mode can defer to a per-request
    ``VariantService`` and stdio mode can hold a directly constructed instance.
    """
    mcp: FastMCP = FastMCP(
        name="litvar-link",
        instructions=INSTRUCTIONS,
        mask_error_details=True,
    )
    register_all(mcp, service_factory=service_factory)
    return mcp
