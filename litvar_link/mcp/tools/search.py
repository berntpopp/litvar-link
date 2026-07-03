"""MCP tool: search_genetic_variants."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Annotated, Any, Literal

from fastmcp.tools.tool import ToolResult
from pydantic import Field

from litvar_link.exceptions import ValidationError
from litvar_link.mcp.errors import ToolValidationError, run_tool
from litvar_link.mcp.shaping import DEFAULT_LIMIT, apply_limit, shape_variant_row
from litvar_link.validation import validate_limit, validate_query

if TYPE_CHECKING:
    from fastmcp import FastMCP


def register(mcp: FastMCP, *, service_factory: Callable[[], Any]) -> None:
    """Register the search_genetic_variants tool."""

    @mcp.tool(
        name="search_genetic_variants",
        title="Search Genetic Variants",
        tags={"variant"},
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
            shaped["query"] = clean_query
            shaped["cached"] = response.cached
            return shaped

        return await run_tool("search_genetic_variants", body)
