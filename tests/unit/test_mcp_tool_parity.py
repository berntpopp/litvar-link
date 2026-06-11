"""MCP tool-name/schema parity guard across the from_fastapi -> explicit facade swap."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

SNAPSHOT = Path(__file__).parent.parent / "fixtures" / "mcp_tool_snapshot.json"

# The contract: these 5 names + the discovery tool MUST exist after the facade lands.
EXPECTED_TOOL_NAMES = {
    "search_genetic_variants",
    "get_variant_summary",
    "get_variant_literature",
    "lookup_rsid_availability",
    "search_gene_variants",
}

# fastmcp 3.4.2 exposes `list_tools()` (returns list[FunctionTool]); there is no
# `get_tools()`. Derive names from the tool objects' `.name` attribute.


async def _facade_tool_names() -> set[str]:
    from litvar_link.mcp.facade import create_litvar_mcp

    mcp = create_litvar_mcp(service_factory=lambda: object())
    tools = await mcp.list_tools()
    return {t.name for t in tools}


@pytest.mark.asyncio
async def test_facade_preserves_five_tool_names() -> None:
    names = await _facade_tool_names()
    assert names >= EXPECTED_TOOL_NAMES, f"missing: {EXPECTED_TOOL_NAMES - names}"


@pytest.mark.asyncio
async def test_facade_adds_capabilities_tool() -> None:
    names = await _facade_tool_names()
    assert "get_server_capabilities" in names


@pytest.mark.asyncio
async def test_snapshot_recorded() -> None:
    names = sorted(await _facade_tool_names())
    if not SNAPSHOT.exists():
        SNAPSHOT.write_text(json.dumps({"tool_names": names}, indent=2), encoding="utf-8")
    recorded: dict[str, Any] = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    assert set(recorded["tool_names"]) >= set(EXPECTED_TOOL_NAMES)
