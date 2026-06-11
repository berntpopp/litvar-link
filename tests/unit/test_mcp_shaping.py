"""Unit tests for MCP error split, response shaping, limits, and citation."""

from __future__ import annotations

import pytest

from litvar_link.mcp.capabilities import INSTRUCTIONS, server_capabilities
from litvar_link.mcp.errors import ToolValidationError, run_tool
from litvar_link.mcp.shaping import (
    DEFAULT_LIMIT,
    MAX_LIMIT,
    apply_limit,
    recommended_citation,
    shape_variant_row,
)


class TestErrors:
    @pytest.mark.asyncio
    async def test_validation_error_is_visible(self) -> None:
        async def body() -> dict[str, str]:
            raise ToolValidationError("empty query")

        # Recoverable validation errors propagate (visible to the agent).
        with pytest.raises(ToolValidationError):
            await run_tool("search_genetic_variants", body)

    @pytest.mark.asyncio
    async def test_internal_error_is_masked(self) -> None:
        async def body() -> dict[str, str]:
            raise RuntimeError("secret db path /etc/x leaked")

        with pytest.raises(Exception) as exc:  # asserting masking below
            await run_tool("search_genetic_variants", body)
        assert "secret db path" not in str(exc.value)
        assert "search_genetic_variants" in str(exc.value)


class TestShaping:
    def test_apply_limit_truncates_with_markers(self) -> None:
        rows = list(range(10))
        out = apply_limit(rows, limit=3)
        assert out["results"] == [0, 1, 2]
        assert out["truncated"] is True
        assert out["total"] == 10
        assert out["returned"] == 3

    def test_apply_limit_no_truncation(self) -> None:
        out = apply_limit([1, 2], limit=5)
        assert out["truncated"] is False
        assert out["total"] == 2

    def test_compact_row_drops_heavy_fields(self) -> None:
        full = {
            "_id": "litvar@rs1##",
            "rsid": "rs1",
            "gene": ["CFH"],
            "name": "p.Y402H",
            "pmids_count": 5,
            "match": "<em>..</em>",
            "hgvs": "NP_x",
        }
        compact = shape_variant_row(full, mode="compact")
        assert "match" not in compact
        assert compact["rsid"] == "rs1"

    def test_full_row_passthrough(self) -> None:
        full = {"_id": "x", "match": "keep"}
        assert shape_variant_row(full, mode="full") == full

    def test_recommended_citation_from_pmid(self) -> None:
        cite = recommended_citation("32511357")
        assert "32511357" in cite
        assert "pubmed" in cite.lower()


class TestCapabilities:
    def test_server_capabilities_payload(self) -> None:
        caps = server_capabilities()
        assert caps["server"] == "litvar-link"
        assert "search_genetic_variants" in caps["tools"]
        assert "get_server_capabilities" in caps["tools"]
        assert caps["response_modes"] == ["compact", "full"]
        assert caps["limit"] == {"default": DEFAULT_LIMIT, "max": MAX_LIMIT}
        assert "recommended_citation" in caps["citation_contract"]
        assert "Research use only" in caps["research_use_only"]

    def test_instructions_mention_tools_and_citation(self) -> None:
        assert "search_genetic_variants" in INSTRUCTIONS
        assert "recommended_citation" in INSTRUCTIONS
        assert "get_server_capabilities" in INSTRUCTIONS
