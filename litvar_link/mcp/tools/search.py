"""MCP tool: search_genetic_variants."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Annotated, Any, Literal

from fastmcp.tools.tool import ToolResult
from pydantic import Field

from litvar_link.exceptions import ValidationError
from litvar_link.mcp.errors import ToolValidationError, run_tool
from litvar_link.mcp.shaping import (
    DEFAULT_LIMIT,
    MAX_LIMIT,
    apply_limit,
    collect_fenced_matches,
    shape_variant_row,
    untrusted_text_field_schema,
)
from litvar_link.mcp.untrusted_content import enforce_untrusted_text_limits
from litvar_link.validation import validate_limit, validate_query

if TYPE_CHECKING:
    from fastmcp import FastMCP

_MATCH_SCHEMA, _MATCH_DEFS = untrusted_text_field_schema()

# Advertises the ``untrusted_text`` object shape (``kind`` const included) for
# the full-mode ``results[*].match`` field in the array-ITEM schema itself --
# a bare permissive array would hide the literal even though the runtime data
# is fenced (Response-Envelope Standard v1.1). ``additionalProperties: True``
# on the item and top level preserves ``full`` mode's raw-passthrough contract
# for every other upstream field.
SEARCH_GENETIC_VARIANTS_OUTPUT_SCHEMA: dict[str, Any] = {
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
        "query": {"type": "string"},
        "cached": {"type": "boolean"},
    },
    "required": ["results", "returned", "total", "truncated"],
    "additionalProperties": True,
    "$defs": _MATCH_DEFS,
}


def register(mcp: FastMCP, *, service_factory: Callable[[], Any]) -> None:
    """Register the search_genetic_variants tool."""

    @mcp.tool(
        name="search_genetic_variants",
        title="Search Genetic Variants",
        tags={"variant"},
        output_schema=SEARCH_GENETIC_VARIANTS_OUTPUT_SCHEMA,
    )
    async def search_genetic_variants(
        query: Annotated[
            str,
            Field(description="Gene symbol, variant name, RSID, or HGVS text."),
        ],
        limit: Annotated[
            int,
            Field(description=f"Max results (default {DEFAULT_LIMIT}, max 100)."),
        ] = DEFAULT_LIMIT,
        response_mode: Annotated[
            Literal["compact", "full"],
            Field(description="compact (high-signal fields) or full (raw payload)."),
        ] = "compact",
    ) -> dict[str, Any] | ToolResult:
        """Resolve free-text/gene/RSID/HGVS into LitVar2 variant rows.

        Research use only; not clinical decision support.
        """

        async def body() -> dict[str, Any]:
            try:
                clean_query = validate_query(query)
                clean_limit = validate_limit(limit)
            except ValidationError as exc:
                raise ToolValidationError(str(exc)) from exc
            response = await service_factory().search_variants(
                query=clean_query,
                limit=clean_limit,
            )
            rows = [
                shape_variant_row(v.model_dump(), mode=response_mode) for v in response.variants
            ]
            shaped = apply_limit(rows, limit=clean_limit)
            if response_mode == "full":
                # Aggregate every fenced object across the WHOLE response (all
                # rows, not per-record) into one enforce call. max_objects =
                # MAX_LIMIT: the tool's own real result cap (not the generic
                # 128 default), since this tool can never return more than
                # MAX_LIMIT rows in one response.
                enforce_untrusted_text_limits(
                    collect_fenced_matches(shaped["results"]), max_objects=MAX_LIMIT
                )
            shaped["query"] = clean_query
            shaped["cached"] = response.cached
            return shaped

        return await run_tool("search_genetic_variants", body)
