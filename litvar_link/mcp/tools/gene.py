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
    ResponseMode,
    decode_cursor,
    paginate,
    shape_variant_row,
)
from litvar_link.validation import validate_gene_name

if TYPE_CHECKING:
    from fastmcp import FastMCP


# Parameter types hoisted to module level: the tool signature stays inside the
# per-function LOC budget WITHOUT shortening a single description (descriptions
# are what the model reads -- TOOL-SCHEMA-DOCUMENTATION-STANDARD S1/S6).
GeneSymbolParam = Annotated[
    str,
    Field(description="HGNC gene symbol, e.g. CFH.", examples=["BRCA1"]),
]
LimitParam = Annotated[
    int,
    Field(
        description=f"Max variants per page (default {DEFAULT_LIMIT}, max {MAX_LIMIT}).",
        ge=1,
        le=MAX_LIMIT,
        examples=[25],
    ),
]
CursorParam = Annotated[
    str | None,
    Field(
        description=(
            "Opaque pagination cursor from a previous call's "
            "`_meta.pagination.next_cursor`. Omit for the first page."
        ),
        examples=["bzoyNQ"],
    ),
]
ResponseModeParam = Annotated[
    Literal["compact", "full"],
    Field(description="compact (high-signal fields) or full (raw payload)."),
]


_NO_CLASSIFICATIONS_NOTE = (
    "LitVar2's gene endpoint supplies no clinical significance for these variants, so NONE is "
    "reported here -- this is not evidence of absent pathogenicity. Call get_variant_summary "
    "for a specific variant's reported significance."
)


def _add_classification_counts(shaped: dict[str, Any], resp: Any) -> None:
    """Publish significance counts ONLY if LitVar2 actually classified something.

    It does not on this endpoint -- the rows carry only {id, rsid, pmids_count} --
    so the old code recoded every absent field as "uncertain" and COUNTED it,
    publishing "13,264 BRCA1 variants, 0 pathogenic, 13,264 uncertain". Absent is
    UNKNOWN, and an unknown must never be reported as a negative finding (#66 D3).

    The counts describe the gene's WHOLE variant set, not just this page.
    """
    classified = resp.classified_count
    shaped["classifications_available"] = classified > 0
    shaped["unclassified_count"] = resp.unclassified_count
    if classified > 0:
        shaped["classified_count"] = classified
        shaped["pathogenic_count"] = resp.pathogenic_count
        shaped["benign_count"] = resp.benign_count
        shaped["uncertain_count"] = resp.uncertain_count
    else:
        shaped["classification_note"] = _NO_CLASSIFICATIONS_NOTE


async def _gene_body(
    service: Any,
    *,
    gene_symbol: str,
    limit: int,
    cursor: str | None,
    response_mode: ResponseMode,
) -> dict[str, Any]:
    """Fetch a gene's variants and shape an honest page."""
    try:
        clean = validate_gene_name(gene_symbol)
        offset = decode_cursor(cursor)
    except ValidationError as exc:
        raise ToolValidationError(str(exc)) from exc

    resp = await service.search_gene_variants(clean)
    rows = [shape_variant_row(v.model_dump(), mode=response_mode) for v in resp.variants]
    # The gene endpoint returns EVERY variant, so total_count is the real upstream
    # figure -- and the cursor can now reach all 13,264 of them.
    shaped = paginate(rows, limit=limit, offset=offset, total_count=len(rows))
    shaped["gene"] = clean
    shaped["cached"] = resp.cached
    _add_classification_counts(shaped, resp)
    return shaped


def register(mcp: FastMCP, *, service_factory: Callable[[], Any]) -> None:
    """Register the search_gene_variants tool."""

    @mcp.tool(
        name="search_gene_variants",
        title="Search Gene Variants",
        tags={"gene", "variant"},
        output_schema=None,  # Tool-Surface Budget v1 B3: structuredContent is unaffected.
        annotations=READ_ONLY_OPEN_WORLD,
    )
    async def search_gene_variants(
        gene_symbol: GeneSymbolParam,
        limit: LimitParam = DEFAULT_LIMIT,
        cursor: CursorParam = None,
        response_mode: ResponseModeParam = "compact",
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
            return await _gene_body(
                service_factory(),
                gene_symbol=gene_symbol,
                limit=limit,
                cursor=cursor,
                response_mode=response_mode,
            )

        return await run_tool("search_gene_variants", body)
