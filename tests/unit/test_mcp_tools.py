"""Each tool module registers exactly its tool and calls through to the service.

Success responses are asserted against the flat Response-Envelope Standard v1
banner (``success``/payload/``_meta``); failures are asserted against the flat
in-band error frame returned (never raised) as a ``ToolResult(is_error=True)``.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastmcp import FastMCP
from fastmcp.tools.tool import ToolResult

from litvar_link.mcp.tools import register_all


def _service() -> AsyncMock:
    return AsyncMock()


async def _tool_by_name(mcp: FastMCP, name: str) -> Any:
    tools = await mcp.list_tools()
    return next(t for t in tools if t.name == name)


def _error_payload(result: Any) -> dict[str, Any]:
    assert isinstance(result, ToolResult)
    assert result.is_error is True
    payload: dict[str, Any] = result.structured_content or {}
    assert payload["success"] is False
    return payload


@pytest.mark.asyncio
async def test_register_all_adds_five_capability_tools() -> None:
    mcp = FastMCP(name="t")
    register_all(mcp, service_factory=_service)
    names = {t.name for t in await mcp.list_tools()}
    assert names >= {
        "search_genetic_variants",
        "get_variant_summary",
        "get_variant_literature",
        "resolve_rsid",
        "search_gene_variants",
    }


@pytest.mark.asyncio
async def test_search_tool_invokes_service_and_shapes() -> None:
    svc = _service()
    svc.search_variants = AsyncMock(
        return_value=SimpleNamespace(
            variants=[
                SimpleNamespace(
                    model_dump=lambda: {
                        "id": "litvar@rs1##",
                        "rsid": "rs1",
                        "gene": ["CFH"],
                        "name": "p.Y",
                        "pmids_count": 3,
                        "match": "x",
                    }
                )
            ],
            total_count=1,
            has_more=False,
            cached=False,
        )
    )
    mcp = FastMCP(name="t")
    register_all(mcp, service_factory=lambda: svc)
    tool = await _tool_by_name(mcp, "search_genetic_variants")
    result = await tool.run({"query": "CFH", "limit": 10, "response_mode": "compact"})
    payload: dict[str, Any] = result.structured_content or {}
    assert payload["success"] is True
    assert payload["returned"] == 1
    assert "match" not in payload["results"][0]  # compact drops it
    assert payload["query"] == "CFH"
    assert payload["_meta"]["tool"] == "search_genetic_variants"
    assert payload["_meta"]["unsafe_for_clinical_use"] is True
    assert payload["_meta"]["request_id"]
    # Autocomplete supplies no count: null is honest, a fabricated total is not.
    assert payload["_meta"]["pagination"] == {
        "total_count": None,
        "has_more": False,
        "next_cursor": None,
    }


@pytest.mark.asyncio
async def test_search_tool_validation_error_is_visible() -> None:
    svc = _service()
    mcp = FastMCP(name="t")
    register_all(mcp, service_factory=lambda: svc)
    tool = await _tool_by_name(mcp, "search_genetic_variants")
    result = await tool.run({"query": "", "limit": 10, "response_mode": "compact"})
    payload = _error_payload(result)
    assert payload["error_code"] == "invalid_input"
    assert "empty" in payload["message"].lower()
    assert payload["retryable"] is False
    assert payload["recovery_action"]


@pytest.mark.asyncio
async def test_variant_summary_tool_compacts_variant() -> None:
    svc = _service()
    svc.get_variant_summary = AsyncMock(
        return_value=SimpleNamespace(
            model_dump=lambda: {
                "variant": {
                    "id": "litvar@rs1##",
                    "rsid": "rs1",
                    "gene": ["CFH"],
                    "name": "p.Y",
                    "pmids_count": 3,
                    "match": "drop-me",
                },
                "cached": False,
            }
        )
    )
    mcp = FastMCP(name="t")
    register_all(mcp, service_factory=lambda: svc)
    tool = await _tool_by_name(mcp, "get_variant_summary")
    result = await tool.run({"variant_id": "litvar@rs1##", "response_mode": "compact"})
    payload: dict[str, Any] = result.structured_content or {}
    assert payload["success"] is True
    assert "match" not in payload["result"]
    assert payload["result"]["rsid"] == "rs1"
    assert payload["cached"] is False


@pytest.mark.asyncio
async def test_variant_summary_empty_id_raises() -> None:
    svc = _service()
    mcp = FastMCP(name="t")
    register_all(mcp, service_factory=lambda: svc)
    tool = await _tool_by_name(mcp, "get_variant_summary")
    result = await tool.run({"variant_id": "  ", "response_mode": "compact"})
    payload = _error_payload(result)
    assert payload["error_code"] == "invalid_input"
    assert "empty" in payload["message"].lower()


@pytest.mark.asyncio
async def test_variant_summary_service_validation_error_is_visible() -> None:
    from litvar_link.exceptions import ValidationError

    svc = _service()
    svc.get_variant_summary = AsyncMock(
        side_effect=ValidationError("bad variant id", field="variant_id")
    )
    mcp = FastMCP(name="t")
    register_all(mcp, service_factory=lambda: svc)
    tool = await _tool_by_name(mcp, "get_variant_summary")
    result = await tool.run({"variant_id": "x", "response_mode": "compact"})
    payload = _error_payload(result)
    assert payload["error_code"] == "invalid_input"
    assert "bad variant id" in payload["message"]


@pytest.mark.asyncio
async def test_literature_tool_adds_recommended_citation() -> None:
    svc = _service()
    svc.get_variant_literature = AsyncMock(
        return_value=SimpleNamespace(
            publications=[SimpleNamespace(pmid="32511357"), SimpleNamespace(pmid="123")],
            cached=True,
        )
    )
    mcp = FastMCP(name="t")
    register_all(mcp, service_factory=lambda: svc)
    tool = await _tool_by_name(mcp, "get_variant_literature")
    result = await tool.run({"variant_id": "litvar@rs1##", "limit": 25})
    payload: dict[str, Any] = result.structured_content or {}
    assert payload["success"] is True
    assert payload["returned"] == 2
    first = payload["results"][0]
    assert first["pmid"] == "32511357"
    assert "32511357" in first["recommended_citation"]
    assert payload["cached"] is True


@pytest.mark.asyncio
async def test_literature_tool_empty_id_raises() -> None:
    svc = _service()
    mcp = FastMCP(name="t")
    register_all(mcp, service_factory=lambda: svc)
    tool = await _tool_by_name(mcp, "get_variant_literature")
    result = await tool.run({"variant_id": "", "limit": 25})
    payload = _error_payload(result)
    assert payload["error_code"] == "invalid_input"
    assert "empty" in payload["message"].lower()


@pytest.mark.asyncio
async def test_literature_tool_service_validation_error_is_visible() -> None:
    from litvar_link.exceptions import ValidationError

    svc = _service()
    svc.get_variant_literature = AsyncMock(
        side_effect=ValidationError("bad variant id", field="variant_id")
    )
    mcp = FastMCP(name="t")
    register_all(mcp, service_factory=lambda: svc)
    tool = await _tool_by_name(mcp, "get_variant_literature")
    result = await tool.run({"variant_id": "x", "limit": 25})
    payload = _error_payload(result)
    assert payload["error_code"] == "invalid_input"
    assert "bad variant id" in payload["message"]


@pytest.mark.asyncio
async def test_rsid_tool_invokes_service() -> None:
    svc = _service()
    svc.lookup_rsid = AsyncMock(
        return_value=SimpleNamespace(model_dump=lambda: {"rsid": "rs1061170", "available": True})
    )
    mcp = FastMCP(name="t")
    register_all(mcp, service_factory=lambda: svc)
    tool = await _tool_by_name(mcp, "resolve_rsid")
    result = await tool.run({"variant_id": "rs1061170"})
    payload: dict[str, Any] = result.structured_content or {}
    assert payload["success"] is True
    assert payload["result"]["rsid"] == "rs1061170"
    assert payload["result"]["available"] is True


@pytest.mark.asyncio
async def test_rsid_tool_invalid_raises() -> None:
    svc = _service()
    mcp = FastMCP(name="t")
    register_all(mcp, service_factory=lambda: svc)
    tool = await _tool_by_name(mcp, "resolve_rsid")
    result = await tool.run({"variant_id": "not-an-rsid"})
    payload = _error_payload(result)
    assert payload["error_code"] == "invalid_input"
    assert "rsid" in payload["message"].lower()


@pytest.mark.asyncio
async def test_gene_tool_invokes_service_and_shapes() -> None:
    svc = _service()
    svc.search_gene_variants = AsyncMock(
        return_value=SimpleNamespace(
            variants=[
                SimpleNamespace(
                    model_dump=lambda: {
                        "id": "litvar@rs1##",
                        "rsid": "rs1",
                        "pmids_count": 3,
                        "match": "x",
                    }
                )
            ],
            pathogenic_count=1,
            benign_count=0,
            uncertain_count=0,
            cached=False,
        )
    )
    mcp = FastMCP(name="t")
    register_all(mcp, service_factory=lambda: svc)
    tool = await _tool_by_name(mcp, "search_gene_variants")
    result = await tool.run({"gene_symbol": "CFH", "limit": 10, "response_mode": "compact"})
    payload: dict[str, Any] = result.structured_content or {}
    assert payload["success"] is True
    assert payload["gene"] == "CFH"
    assert payload["pathogenic_count"] == 1
    assert "match" not in payload["results"][0]


@pytest.mark.asyncio
async def test_gene_tool_empty_raises() -> None:
    svc = _service()
    mcp = FastMCP(name="t")
    register_all(mcp, service_factory=lambda: svc)
    tool = await _tool_by_name(mcp, "search_gene_variants")
    result = await tool.run({"gene_symbol": "", "limit": 10, "response_mode": "compact"})
    payload = _error_payload(result)
    assert payload["error_code"] == "invalid_input"
    assert "empty" in payload["message"].lower()


@pytest.mark.asyncio
async def test_internal_error_is_masked() -> None:
    svc = _service()
    svc.search_variants = AsyncMock(side_effect=RuntimeError("secret /etc/passwd leaked"))
    mcp = FastMCP(name="t")
    register_all(mcp, service_factory=lambda: svc)
    tool = await _tool_by_name(mcp, "search_genetic_variants")
    result = await tool.run({"query": "CFH", "limit": 10, "response_mode": "compact"})
    payload = _error_payload(result)
    assert payload["error_code"] == "internal"
    assert "secret" not in payload["message"]
    assert payload["retryable"] is False


# --- Real protocol path: mcp.call_tool() -------------------------------------
# tool.run() bypasses FastMCP's outer masking boundary; agents reach tools via
# the MCP `tools/call` method, which routes through call_tool(). run_tool()
# never raises, so call_tool() returns a ToolResult(is_error=True) instead of
# raising -- these tests pin that on the real protocol path.


@pytest.mark.asyncio
async def test_call_tool_surfaces_validation_message() -> None:
    svc = _service()
    mcp = FastMCP(name="t", mask_error_details=True)
    register_all(mcp, service_factory=lambda: svc)
    result = await mcp.call_tool(
        "search_genetic_variants",
        {"query": "", "limit": 10, "response_mode": "compact"},
    )
    payload = _error_payload(result)
    # The actionable message reaches the agent (NOT masked to a generic string).
    assert "empty" in payload["message"].lower()


@pytest.mark.asyncio
async def test_call_tool_masks_internal_detail_but_keeps_request_id() -> None:
    svc = _service()
    svc.search_variants = AsyncMock(side_effect=RuntimeError("secret /etc/passwd leaked"))
    mcp = FastMCP(name="t", mask_error_details=True)
    register_all(mcp, service_factory=lambda: svc)
    result = await mcp.call_tool(
        "search_genetic_variants",
        {"query": "CFH", "limit": 10, "response_mode": "compact"},
    )
    payload = _error_payload(result)
    assert "secret" not in payload["message"]  # no upstream detail leaks
    assert payload["_meta"]["request_id"]  # but a support handle reaches the agent
