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
    MAX_LIMIT,
    decode_cursor,
    paginate,
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
        "gene": {"type": "string"},
        "classifications_available": {"type": "boolean"},
        "unclassified_count": {"type": "integer"},
        "classified_count": {"type": "integer"},
        "pathogenic_count": {"type": "integer"},
        "benign_count": {"type": "integer"},
        "uncertain_count": {"type": "integer"},
        "classification_note": {"type": "string"},
        "cached": {"type": "boolean"},
    },
    "required": ["results", "returned", "classifications_available"],
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
        gene_symbol: Annotated[
            str,
            Field(description="HGNC gene symbol, e.g. CFH.", examples=["BRCA1"]),
        ],
        limit: Annotated[
            int,
            Field(
                description=f"Max variants per page (default {DEFAULT_LIMIT}, max {MAX_LIMIT}).",
                ge=1,
                le=MAX_LIMIT,
                examples=[25],
            ),
        ] = DEFAULT_LIMIT,
        cursor: Annotated[
            str | None,
            Field(
                description=(
                    "Opaque pagination cursor from a previous call's "
                    "`_meta.pagination.next_cursor`. Omit for the first page."
                ),
                examples=["bzoyNQ"],
            ),
        ] = None,
        response_mode: Annotated[
            Literal["compact", "full"],
            Field(description="compact (high-signal fields) or full (raw payload)."),
        ] = "compact",
    ) -> dict[str, Any] | ToolResult:
        """Return LitVar2 variants for a gene symbol, with the gene's TRUE variant
        count in `_meta.pagination.total_count` (BRCA1 has 13,264).

        Page through the whole set with `_meta.pagination.next_cursor`.

        CLINICAL SIGNIFICANCE IS NOT AVAILABLE HERE. LitVar2's gene endpoint
        returns only `{id, rsid, pmids_count}` per row, so this tool reports
        `classifications_available: false` and emits NO pathogenic/benign counts.
        Absence of a classification here is NOT evidence that a variant is benign.
        Call `get_variant_summary` for a specific variant's reported significance.

        Research use only; not clinical decision support.
        """

        async def body() -> dict[str, Any]:
            try:
                clean = validate_gene_name(gene_symbol)
                offset = decode_cursor(cursor)
            except ValidationError as exc:
                raise ToolValidationError(str(exc)) from exc
            resp = await service_factory().search_gene_variants(clean)
            rows = [shape_variant_row(v.model_dump(), mode=response_mode) for v in resp.variants]
            # The gene endpoint returns EVERY variant, so total_count is the real
            # upstream figure -- and the cursor can now reach all 13,264 of them.
            shaped = paginate(rows, limit=limit, offset=offset, total_count=len(rows))
            shaped["gene"] = clean
            shaped["cached"] = resp.cached

            # Emit the significance counts ONLY if LitVar2 actually classified
            # something. It does not on this endpoint -- the rows carry only
            # {id, rsid, pmids_count} -- so the old code recoded every absent
            # field as "uncertain" and COUNTED it, publishing "13,264 BRCA1
            # variants, 0 pathogenic, 13,264 uncertain". Absent is UNKNOWN, and
            # an unknown must never be reported as a negative finding.
            # The counts describe the gene's WHOLE variant set, not just this page.
            shaped["classifications_available"] = resp.classified_count > 0
            shaped["unclassified_count"] = resp.unclassified_count
            if resp.classified_count > 0:
                shaped["classified_count"] = resp.classified_count
                shaped["pathogenic_count"] = resp.pathogenic_count
                shaped["benign_count"] = resp.benign_count
                shaped["uncertain_count"] = resp.uncertain_count
            else:
                shaped["classification_note"] = (
                    "LitVar2's gene endpoint supplies no clinical significance for these "
                    "variants, so NONE is reported here -- this is not evidence of absent "
                    "pathogenicity. Call get_variant_summary for a specific variant's "
                    "reported significance."
                )
            return shaped

        return await run_tool("search_gene_variants", body)
