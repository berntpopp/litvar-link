"""Tool registration entry points for the LitVar-Link MCP facade."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from litvar_link.mcp.tools import gene, literature, metadata, rsid, search, variant

if TYPE_CHECKING:
    from fastmcp import FastMCP


def register_all(mcp: FastMCP, *, service_factory: Callable[[], Any]) -> None:
    """Register every LitVar-Link tool group on the FastMCP server."""
    search.register(mcp, service_factory=service_factory)
    variant.register(mcp, service_factory=service_factory)
    literature.register(mcp, service_factory=service_factory)
    rsid.register(mcp, service_factory=service_factory)
    gene.register(mcp, service_factory=service_factory)
    metadata.register(mcp, service_factory=service_factory)
