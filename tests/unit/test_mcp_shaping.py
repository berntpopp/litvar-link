"""Unit tests for MCP error split, response shaping, limits, and citation."""

from __future__ import annotations

from typing import Any

import pytest
from fastmcp.tools.tool import ToolResult

from litvar_link.exceptions import LitVarAPIError, RateLimitError, ServiceUnavailableError
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
        async def body() -> dict[str, Any]:
            raise ToolValidationError("empty query")

        # Recoverable validation errors are RETURNED as a flat in-band envelope
        # (never raised) per the Response-Envelope Standard v1.
        result = await run_tool("search_genetic_variants", body)
        assert isinstance(result, ToolResult)
        assert result.is_error is True
        payload = result.structured_content or {}
        assert payload["success"] is False
        assert payload["error_code"] == "invalid_input"
        assert "empty query" in payload["message"]

    @pytest.mark.asyncio
    async def test_internal_error_is_masked(self) -> None:
        async def body() -> dict[str, Any]:
            raise RuntimeError("secret db path /etc/x leaked")

        result = await run_tool("search_genetic_variants", body)
        assert isinstance(result, ToolResult)
        assert result.is_error is True
        payload = result.structured_content or {}
        assert payload["success"] is False
        assert payload["error_code"] == "internal"
        assert "secret db path" not in payload["message"]
        assert "search_genetic_variants" in payload["message"]
        assert payload["_meta"]["request_id"]

    @pytest.mark.asyncio
    async def test_rate_limit_error_is_retryable(self) -> None:
        async def body() -> dict[str, Any]:
            raise RateLimitError("Rate limit exceeded", retry_after=30.0)

        result = await run_tool("search_genetic_variants", body)
        assert isinstance(result, ToolResult)
        payload = result.structured_content or {}
        assert payload["error_code"] == "rate_limited"
        assert payload["retryable"] is True

    @pytest.mark.asyncio
    async def test_service_unavailable_error_is_retryable(self) -> None:
        async def body() -> dict[str, Any]:
            raise ServiceUnavailableError()

        result = await run_tool("search_genetic_variants", body)
        assert isinstance(result, ToolResult)
        payload = result.structured_content or {}
        assert payload["error_code"] == "upstream_unavailable"
        assert payload["retryable"] is True

    @pytest.mark.asyncio
    async def test_api_error_404_maps_to_not_found(self) -> None:
        async def body() -> dict[str, Any]:
            raise LitVarAPIError("HTTP 404: not found", status_code=404)

        result = await run_tool("resolve_rsid", body)
        assert isinstance(result, ToolResult)
        payload = result.structured_content or {}
        assert payload["error_code"] == "not_found"
        assert payload["retryable"] is False

    @pytest.mark.asyncio
    async def test_api_error_other_4xx_maps_to_invalid_input(self) -> None:
        async def body() -> dict[str, Any]:
            raise LitVarAPIError("HTTP 400: bad request", status_code=400)

        result = await run_tool("resolve_rsid", body)
        assert isinstance(result, ToolResult)
        payload = result.structured_content or {}
        assert payload["error_code"] == "invalid_input"
        assert payload["retryable"] is False

    @pytest.mark.asyncio
    async def test_api_error_without_status_code_is_upstream_unavailable(self) -> None:
        async def body() -> dict[str, Any]:
            raise LitVarAPIError("Unexpected error: boom")

        result = await run_tool("resolve_rsid", body)
        assert isinstance(result, ToolResult)
        payload = result.structured_content or {}
        assert payload["error_code"] == "upstream_unavailable"
        assert payload["retryable"] is True

    @pytest.mark.asyncio
    async def test_timeout_error_is_upstream_unavailable(self) -> None:
        async def body() -> dict[str, Any]:
            raise TimeoutError("deadline exceeded")

        result = await run_tool("resolve_rsid", body)
        assert isinstance(result, ToolResult)
        payload = result.structured_content or {}
        assert payload["error_code"] == "upstream_unavailable"
        assert payload["retryable"] is True

    @pytest.mark.asyncio
    async def test_success_meta_carries_elapsed_ms_and_source(self) -> None:
        async def body() -> dict[str, Any]:
            return {"results": []}

        result = await run_tool("search_genetic_variants", body)
        assert isinstance(result, dict)
        assert result["_meta"]["source"] == "litvar-link"
        assert isinstance(result["_meta"]["elapsed_ms"], int)
        assert result["_meta"]["elapsed_ms"] >= 0


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
        full = {"_id": "x", "gene": ["CFH"]}
        assert shape_variant_row(full, mode="full") == full

    def test_full_row_fences_match_as_untrusted_text(self) -> None:
        full = {"_id": "x", "match": "keep"}
        shaped = shape_variant_row(full, mode="full")
        assert shaped["match"]["kind"] == "untrusted_text"
        assert shaped["match"]["text"] == "keep"
        assert shaped["match"]["provenance"]["source"] == "litvar"
        assert shaped["match"]["provenance"]["record_id"] == "x"

    def test_full_row_without_match_is_unchanged(self) -> None:
        full = {"_id": "x", "match": None}
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
