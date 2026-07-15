"""Tool-Surface Budget v1 + Tool-Schema Documentation v1 regression gates.

The surface is a tax every client pays on EVERY request for the life of the
session, whether or not a tool is ever called. These assert it stays paid down,
and that the schema keeps telling a model what it needs to make a valid call.

Measured the same way the router's `scripts/surface.py` measures it: the
serialized `tools/list` entry, at ~4 characters per token.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from litvar_link.mcp.facade import create_litvar_mcp

# TOOL-SURFACE-BUDGET-STANDARD v1
B1_MAX_TOOL_TOKENS = 1_200
B2_MAX_SERVER_TOKENS = 10_000

_CHARS_PER_TOKEN = 4


def _tokens(obj: Any) -> int:
    return len(json.dumps(obj, separators=(",", ":"))) // _CHARS_PER_TOKEN


async def _tool_defs() -> list[dict[str, Any]]:
    mcp = create_litvar_mcp(service_factory=lambda: object())
    defs: list[dict[str, Any]] = []
    for tool in await mcp.list_tools():
        entry: dict[str, Any] = {
            "name": tool.name,
            "description": tool.description or "",
            "inputSchema": tool.parameters,
        }
        if tool.output_schema is not None:
            entry["outputSchema"] = tool.output_schema
        defs.append(entry)
    return defs


@pytest.mark.asyncio
async def test_b1_no_tool_definition_exceeds_1200_tokens() -> None:
    for tool in await _tool_defs():
        assert _tokens(tool) <= B1_MAX_TOOL_TOKENS, (
            f"{tool['name']} is {_tokens(tool)}t (B1 limit {B1_MAX_TOOL_TOKENS}t). "
            "Cut outputSchema before you cut a description."
        )


@pytest.mark.asyncio
async def test_b2_the_server_surface_stays_under_10000_tokens() -> None:
    defs = await _tool_defs()
    total = sum(_tokens(tool) for tool in defs)
    assert total <= B2_MAX_SERVER_TOKENS, f"surface is {total}t (B2 limit {B2_MAX_SERVER_TOKENS}t)"


@pytest.mark.asyncio
async def test_no_output_schema_is_published() -> None:
    """B3. `outputSchema` was 52% of this server's surface and no model reads it."""
    for tool in await _tool_defs():
        assert "outputSchema" not in tool, tool["name"]


@pytest.mark.asyncio
async def test_s1_every_input_property_carries_a_description() -> None:
    for tool in await _tool_defs():
        for name, prop in (tool["inputSchema"].get("properties") or {}).items():
            assert prop.get("description"), f"{tool['name']}.{name} has no description (S1)"


@pytest.mark.asyncio
async def test_s2_every_required_property_carries_an_example() -> None:
    """Without this, the behaviour gate cannot construct a valid call and reports
    the tool UNGATED -- i.e. nothing about its behaviour is verified at all.
    """
    for tool in await _tool_defs():
        schema = tool["inputSchema"]
        for name in schema.get("required") or []:
            prop = (schema.get("properties") or {}).get(name) or {}
            assert prop.get("examples"), (
                f"{tool['name']}.{name} is required but has no examples (S2)"
            )


@pytest.mark.asyncio
async def test_s3_every_array_property_carries_an_example() -> None:
    for tool in await _tool_defs():
        for name, prop in (tool["inputSchema"].get("properties") or {}).items():
            if prop.get("type") == "array":
                assert prop.get("examples"), (
                    f"{tool['name']}.{name} is an array with no examples (S3)"
                )


@pytest.mark.asyncio
async def test_s4_bounded_numerics_and_closed_vocabularies_are_declared() -> None:
    """An undeclared enum is what produces the silently-empty filter; an
    undeclared bound is what let `limit=0` and `limit=-5` through (audit #10).
    """
    defs = {tool["name"]: tool["inputSchema"] for tool in await _tool_defs()}

    for name, schema in defs.items():
        props = schema.get("properties") or {}
        if "response_mode" in props:
            assert props["response_mode"].get("enum") == ["compact", "full"], name
        if "limit" in props:
            assert props["limit"].get("minimum") == 1, f"{name}.limit has no minimum"
            assert props["limit"].get("maximum") == 100, f"{name}.limit has no maximum"

    assert defs["search_genetic_variants"]["properties"]["query"].get("maxLength") == 100
    assert defs["resolve_rsid"]["properties"]["variant_id"].get("pattern")
