"""MCP safety/schema contract completeness (F-12).

Every LitVar-Link tool must advertise a complete read-only, non-destructive
``ToolAnnotations`` block and a structured ``output_schema`` so hosts (and the
router's drift baseline) can reason about side effects and shape. Missing hints
let a client mis-treat a read-only lookup as mutating, or forgo output
validation entirely.
"""

from __future__ import annotations

from typing import Any

import pytest

from litvar_link.mcp.facade import create_litvar_mcp

_ALL_TOOLS = {
    "search_genetic_variants",
    "get_variant_summary",
    "get_variant_literature",
    "resolve_rsid",
    "search_gene_variants",
    "get_server_capabilities",
}


async def _tools() -> dict[str, Any]:
    mcp = create_litvar_mcp(service_factory=lambda: object())
    return {t.name: t for t in await mcp.list_tools()}


@pytest.mark.asyncio
async def test_every_tool_has_complete_readonly_annotations() -> None:
    tools = await _tools()
    assert set(tools) >= _ALL_TOOLS
    for name in _ALL_TOOLS:
        ann = tools[name].annotations
        assert ann is not None, f"{name} missing ToolAnnotations"
        assert ann.readOnlyHint is True, f"{name} readOnlyHint must be True"
        assert ann.destructiveHint is False, f"{name} destructiveHint must be False"
        assert ann.idempotentHint is True, f"{name} idempotentHint must be True"
        assert ann.openWorldHint is not None, f"{name} openWorldHint must be set"


@pytest.mark.asyncio
async def test_no_tool_publishes_an_output_schema() -> None:
    """Tool-Surface Budget v1 B3: `outputSchema` is the first thing to cut.

    It was 52% of this server's advertised surface, it is OPTIONAL in the MCP
    spec, and no model reads it. Suppressing it does NOT cost us
    `structuredContent` -- every tool returns a dict envelope, and FastMCP still
    emits structuredContent for those (asserted directly in
    test_structured_content_survives_output_schema_none below).
    """
    tools = await _tools()
    for name in _ALL_TOOLS:
        assert tools[name].output_schema is None, (
            f"{name} still advertises an outputSchema; it is 52% of the surface "
            "and nothing reads it (TOOL-SURFACE-BUDGET-STANDARD B3)"
        )


@pytest.mark.asyncio
async def test_structured_content_survives_output_schema_none() -> None:
    """The one hard constraint of B3: a tool returning a bare list/scalar WOULD
    lose structuredContent under output_schema=None. Every litvar tool returns a
    dict envelope, so none do -- prove it on the real wire rather than assume it.
    """
    from fastmcp import Client

    from litvar_link.mcp.facade import create_litvar_mcp

    async with Client(create_litvar_mcp(service_factory=lambda: object())) as client:
        result = await client.call_tool("get_server_capabilities", {}, raise_on_error=False)
        assert isinstance(result.structured_content, dict)
        assert result.structured_content["success"] is True


@pytest.mark.asyncio
async def test_data_tools_are_open_world_capabilities_is_closed() -> None:
    tools = await _tools()
    # The five LitVar2-backed tools reach an external API (open world); the
    # static capabilities tool does not.
    for name in _ALL_TOOLS - {"get_server_capabilities"}:
        assert tools[name].annotations.openWorldHint is True, name
    assert tools["get_server_capabilities"].annotations.openWorldHint is False
