"""The discovery tool returns the inventory + response-surface contract."""

from __future__ import annotations

from typing import Any

import pytest
from fastmcp import FastMCP

from litvar_link.mcp.tools import metadata


async def _tool_by_name(mcp: FastMCP, name: str) -> Any:
    tools = await mcp.list_tools()
    return next(t for t in tools if t.name == name)


@pytest.mark.asyncio
async def test_capabilities_tool_registered_and_returns_contract() -> None:
    mcp = FastMCP(name="t")
    metadata.register(mcp, service_factory=lambda: object())
    names = {t.name for t in await mcp.list_tools()}
    assert "get_server_capabilities" in names
    tool = await _tool_by_name(mcp, "get_server_capabilities")
    result = await tool.run({})
    payload: dict[str, Any] = result.structured_content or {}
    assert payload["server"] == "litvar-link"
    assert "search_genetic_variants" in payload["tools"]
    assert payload["response_modes"] == ["compact", "full"]
    assert "recommended_citation" in payload["citation_contract"]


@pytest.mark.asyncio
async def test_register_all_includes_capabilities_tool() -> None:
    from litvar_link.mcp.tools import register_all

    mcp = FastMCP(name="t")
    register_all(mcp, service_factory=lambda: object())
    names = {t.name for t in await mcp.list_tools()}
    assert "get_server_capabilities" in names
