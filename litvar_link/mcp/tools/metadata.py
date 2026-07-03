"""MCP tool: get_server_capabilities (discovery)."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from fastmcp.tools.tool import ToolResult

from litvar_link.mcp.capabilities import server_capabilities
from litvar_link.mcp.errors import run_tool

if TYPE_CHECKING:
    from fastmcp import FastMCP


def register(mcp: FastMCP, *, service_factory: Callable[[], Any]) -> None:
    """Register the get_server_capabilities discovery tool.

    ``service_factory`` is accepted for a uniform register() signature but unused
    (capabilities are static).
    """

    @mcp.tool(name="get_server_capabilities", title="Get LitVar-Link Capabilities")
    async def get_server_capabilities() -> dict[str, Any] | ToolResult:
        """Discover tools, response modes, limits, the citation contract, and the
        research-use-only notice so a cold client can self-orient."""

        async def body() -> dict[str, Any]:
            return {"result": server_capabilities()}

        return await run_tool("get_server_capabilities", body)
