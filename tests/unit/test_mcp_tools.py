"""Each tool module registers exactly its tool and calls through to the service."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastmcp import FastMCP

from litvar_link.mcp.tools import register_all


def _service() -> AsyncMock:
    return AsyncMock()


async def _tool_by_name(mcp: FastMCP, name: str) -> Any:
    tools = await mcp.list_tools()
    return next(t for t in tools if t.name == name)


@pytest.mark.asyncio
async def test_register_all_adds_five_capability_tools() -> None:
    mcp = FastMCP(name="t")
    register_all(mcp, service_factory=_service)
    names = {t.name for t in await mcp.list_tools()}
    assert names >= {
        "search_genetic_variants",
        "get_variant_summary",
        "get_variant_literature",
        "lookup_rsid_availability",
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
            cached=False,
        )
    )
    mcp = FastMCP(name="t")
    register_all(mcp, service_factory=lambda: svc)
    tool = await _tool_by_name(mcp, "search_genetic_variants")
    result = await tool.run({"query": "CFH", "limit": 10, "response_mode": "compact"})
    payload: dict[str, Any] = result.structured_content or {}
    assert payload["returned"] == 1
    assert "match" not in payload["results"][0]  # compact drops it
    assert payload["query"] == "CFH"


@pytest.mark.asyncio
async def test_search_tool_validation_error_is_visible() -> None:
    svc = _service()
    mcp = FastMCP(name="t")
    register_all(mcp, service_factory=lambda: svc)
    tool = await _tool_by_name(mcp, "search_genetic_variants")
    with pytest.raises(Exception) as exc:  # ToolValidationError surfaces
        await tool.run({"query": "", "limit": 10, "response_mode": "compact"})
    assert "empty" in str(exc.value).lower()


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
    assert "match" not in payload["variant"]
    assert payload["variant"]["rsid"] == "rs1"


@pytest.mark.asyncio
async def test_variant_summary_empty_id_raises() -> None:
    svc = _service()
    mcp = FastMCP(name="t")
    register_all(mcp, service_factory=lambda: svc)
    tool = await _tool_by_name(mcp, "get_variant_summary")
    with pytest.raises(Exception) as exc:
        await tool.run({"variant_id": "  ", "response_mode": "compact"})
    assert "empty" in str(exc.value).lower()


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
    with pytest.raises(Exception) as exc:
        await tool.run({"variant_id": "x", "response_mode": "compact"})
    assert "bad variant id" in str(exc.value)


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
    with pytest.raises(Exception) as exc:
        await tool.run({"variant_id": "", "limit": 25})
    assert "empty" in str(exc.value).lower()


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
    with pytest.raises(Exception) as exc:
        await tool.run({"variant_id": "x", "limit": 25})
    assert "bad variant id" in str(exc.value)


@pytest.mark.asyncio
async def test_rsid_tool_invokes_service() -> None:
    svc = _service()
    svc.lookup_rsid = AsyncMock(
        return_value=SimpleNamespace(model_dump=lambda: {"rsid": "rs1061170", "available": True})
    )
    mcp = FastMCP(name="t")
    register_all(mcp, service_factory=lambda: svc)
    tool = await _tool_by_name(mcp, "lookup_rsid_availability")
    result = await tool.run({"rsid": "rs1061170"})
    payload: dict[str, Any] = result.structured_content or {}
    assert payload["rsid"] == "rs1061170"
    assert payload["available"] is True


@pytest.mark.asyncio
async def test_rsid_tool_invalid_raises() -> None:
    svc = _service()
    mcp = FastMCP(name="t")
    register_all(mcp, service_factory=lambda: svc)
    tool = await _tool_by_name(mcp, "lookup_rsid_availability")
    with pytest.raises(Exception) as exc:
        await tool.run({"rsid": "not-an-rsid"})
    assert "rsid" in str(exc.value).lower()


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
    result = await tool.run({"gene_name": "CFH", "limit": 10, "response_mode": "compact"})
    payload: dict[str, Any] = result.structured_content or {}
    assert payload["gene"] == "CFH"
    assert payload["pathogenic_count"] == 1
    assert "match" not in payload["results"][0]


@pytest.mark.asyncio
async def test_gene_tool_empty_raises() -> None:
    svc = _service()
    mcp = FastMCP(name="t")
    register_all(mcp, service_factory=lambda: svc)
    tool = await _tool_by_name(mcp, "search_gene_variants")
    with pytest.raises(Exception) as exc:
        await tool.run({"gene_name": "", "limit": 10, "response_mode": "compact"})
    assert "empty" in str(exc.value).lower()


@pytest.mark.asyncio
async def test_internal_error_is_masked() -> None:
    svc = _service()
    svc.search_variants = AsyncMock(side_effect=RuntimeError("secret /etc/passwd leaked"))
    mcp = FastMCP(name="t")
    register_all(mcp, service_factory=lambda: svc)
    tool = await _tool_by_name(mcp, "search_genetic_variants")
    with pytest.raises(Exception) as exc:
        await tool.run({"query": "CFH", "limit": 10, "response_mode": "compact"})
    assert "secret" not in str(exc.value)


# --- Real protocol path: mcp.call_tool() with mask_error_details=True --------
# tool.run() bypasses FastMCP's masking boundary; agents reach tools via the
# MCP `tools/call` method, which routes through call_tool(). These tests pin the
# two-class error contract on that real path: recoverable validation errors stay
# visible, internal errors are sanitized to a correlation id with no detail leak.


@pytest.mark.asyncio
async def test_call_tool_surfaces_validation_message() -> None:
    svc = _service()
    mcp = FastMCP(name="t", mask_error_details=True)
    register_all(mcp, service_factory=lambda: svc)
    with pytest.raises(Exception) as exc:
        await mcp.call_tool(
            "search_genetic_variants",
            {"query": "", "limit": 10, "response_mode": "compact"},
        )
    # The actionable message reaches the agent (NOT masked to a generic string).
    assert "empty" in str(exc.value).lower()


@pytest.mark.asyncio
async def test_call_tool_masks_internal_detail_but_keeps_correlation_id() -> None:
    svc = _service()
    svc.search_variants = AsyncMock(side_effect=RuntimeError("secret /etc/passwd leaked"))
    mcp = FastMCP(name="t", mask_error_details=True)
    register_all(mcp, service_factory=lambda: svc)
    with pytest.raises(Exception) as exc:
        await mcp.call_tool(
            "search_genetic_variants",
            {"query": "CFH", "limit": 10, "response_mode": "compact"},
        )
    message = str(exc.value)
    assert "secret" not in message  # no upstream detail leaks
    assert "correlation_id=" in message  # but the support handle reaches the agent
