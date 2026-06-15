"""MCP tool: search_gene_variants."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Annotated, Any, Literal

from pydantic import Field

from litvar_link.exceptions import ValidationError
from litvar_link.mcp.errors import ToolValidationError, run_tool
from litvar_link.mcp.shaping import DEFAULT_LIMIT, apply_limit, shape_variant_row
from litvar_link.validation import validate_gene_name

if TYPE_CHECKING:
    from fastmcp import FastMCP


def register(mcp: FastMCP, *, service_factory: Callable[[], Any]) -> None:
    """Register the search_gene_variants tool."""

    @mcp.tool(
        name="search_gene_variants",
        title="Search Gene Variants",
        tags={"gene", "variant"},
    )
    async def search_gene_variants(
        gene_symbol: Annotated[str, Field(description="HGNC gene symbol, e.g. CFH.")],
        limit: Annotated[
            int,
            Field(description=f"Max variants (default {DEFAULT_LIMIT}, max 100)."),
        ] = DEFAULT_LIMIT,
        response_mode: Annotated[
            Literal["compact", "full"],
            Field(description="compact or full."),
        ] = "compact",
    ) -> dict[str, Any]:
        """Return all LitVar2 variants for a gene symbol. Research use only."""

        async def body() -> dict[str, Any]:
            try:
                clean = validate_gene_name(gene_symbol)
            except ValidationError as exc:
                raise ToolValidationError(str(exc)) from exc
            resp = await service_factory().search_gene_variants(clean)
            rows = [shape_variant_row(v.model_dump(), mode=response_mode) for v in resp.variants]
            shaped = apply_limit(rows, limit=limit)
            shaped["gene"] = clean
            shaped["pathogenic_count"] = resp.pathogenic_count
            shaped["benign_count"] = resp.benign_count
            shaped["uncertain_count"] = resp.uncertain_count
            shaped["cached"] = resp.cached
            return shaped

        return await run_tool("search_gene_variants", body)
