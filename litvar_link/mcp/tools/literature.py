"""MCP tool: get_variant_literature."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Annotated, Any

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
    recommended_citation,
)

if TYPE_CHECKING:
    from fastmcp import FastMCP


# Parameter types hoisted to module level: the tool signature stays inside the
# per-function LOC budget WITHOUT shortening a single description (descriptions
# are what the model reads -- TOOL-SCHEMA-DOCUMENTATION-STANDARD S1/S6).
VariantIdParam = Annotated[
    str,
    Field(
        description=(
            "LitVar id (litvar@rs...##), rsID, or HGVS/free text. "
            "Non-canonical input is resolved via autocomplete."
        ),
        examples=["rs1061170", "litvar@rs1061170##"],
    ),
]
LimitParam = Annotated[
    int,
    Field(
        description=f"Max publications per page (default {DEFAULT_LIMIT}, max {MAX_LIMIT}).",
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


async def _literature_body(
    service: Any,
    *,
    variant_id: str,
    limit: int,
    cursor: str | None,
) -> dict[str, Any]:
    """Fetch a variant's PMIDs and shape an honest page."""
    if not variant_id or not variant_id.strip():
        msg = "variant_id cannot be empty"
        raise ToolValidationError(msg)
    try:
        offset = decode_cursor(cursor)
        resp = await service.get_variant_literature(variant_id.strip())
    except ValidationError as exc:
        raise ToolValidationError(str(exc)) from exc

    rows = [
        {"pmid": pub.pmid, "recommended_citation": recommended_citation(pub.pmid)}
        for pub in resp.publications
        if pub.pmid
    ]
    # The upstream call returns EVERY pmid, so total_count is the real figure and
    # the cursor can reach all of them (885 for rs1061170; 785 of those used to be
    # permanently unreachable through the MCP surface).
    shaped = paginate(rows, limit=limit, offset=offset, total_count=len(rows))
    shaped["variant_id"] = variant_id.strip()
    shaped["cached"] = resp.cached
    return shaped


def register(mcp: FastMCP, *, service_factory: Callable[[], Any]) -> None:
    """Register the get_variant_literature tool."""

    @mcp.tool(
        name="get_variant_literature",
        title="Get Variant Literature",
        tags={"variant", "literature"},
        output_schema=None,  # Tool-Surface Budget v1 B3: structuredContent is unaffected.
        annotations=READ_ONLY_OPEN_WORLD,
    )
    async def get_variant_literature(
        variant_id: VariantIdParam,
        limit: LimitParam = DEFAULT_LIMIT,
        cursor: CursorParam = None,
    ) -> dict[str, Any] | ToolResult:
        """Return PMIDs for a variant; each row carries a recommended_citation.

        Accepts a canonical LitVar id, an rsID, or HGVS/free text -- non-canonical
        input is auto-resolved to the LitVar id via autocomplete. An unresolvable
        variant returns a recoverable "not found" message (use
        search_genetic_variants), not an internal error.

        `_meta.pagination.total_count` is the variant's TRUE publication count;
        page through it with `_meta.pagination.next_cursor`.

        Research use only; not clinical decision support.
        """

        async def body() -> dict[str, Any]:
            return await _literature_body(
                service_factory(),
                variant_id=variant_id,
                limit=limit,
                cursor=cursor,
            )

        return await run_tool("get_variant_literature", body)
