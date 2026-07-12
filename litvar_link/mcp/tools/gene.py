"""MCP tool: search_gene_variants."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Annotated, Any, Literal

from fastmcp.tools.tool import ToolResult
from pydantic import Field

from litvar_link.exceptions import ValidationError
from litvar_link.mcp.annotations import READ_ONLY_OPEN_WORLD
from litvar_link.mcp.errors import ToolValidationError, run_tool
from litvar_link.mcp.shaping import (
    DEFAULT_LIMIT,
    apply_limit,
    shape_variant_row,
    untrusted_text_field_schema,
)
from litvar_link.validation import validate_gene_name

if TYPE_CHECKING:
    from fastmcp import FastMCP

_MATCH_SCHEMA, _MATCH_DEFS = untrusted_text_field_schema()

# Mirrors ``search_genetic_variants``: the full-mode ``results[*].match`` field
# is a fenced ``untrusted_text`` object (Response-Envelope v1.1), declared in the
# array-item schema; ``additionalProperties: True`` preserves full-mode
# raw-passthrough for every other upstream field plus the gene/count summary.
SEARCH_GENE_VARIANTS_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"match": _MATCH_SCHEMA},
                "additionalProperties": True,
            },
        },
        "returned": {"type": "integer"},
        "total": {"type": "integer"},
        "truncated": {"type": "boolean"},
        "gene": {"type": "string"},
        "pathogenic_count": {"type": "integer"},
        "benign_count": {"type": "integer"},
        "uncertain_count": {"type": "integer"},
        "cached": {"type": "boolean"},
    },
    "required": ["results", "returned", "total", "truncated"],
    "additionalProperties": True,
    "$defs": _MATCH_DEFS,
}


def register(mcp: FastMCP, *, service_factory: Callable[[], Any]) -> None:
    """Register the search_gene_variants tool."""

    @mcp.tool(
        name="search_gene_variants",
        title="Search Gene Variants",
        tags={"gene", "variant"},
        output_schema=SEARCH_GENE_VARIANTS_OUTPUT_SCHEMA,
        annotations=READ_ONLY_OPEN_WORLD,
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
    ) -> dict[str, Any] | ToolResult:
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
