"""MCP tool: get_variant_literature."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Annotated, Any

from fastmcp.tools.tool import ToolResult
from pydantic import Field

from litvar_link.exceptions import ValidationError
from litvar_link.mcp.errors import ToolValidationError, run_tool
from litvar_link.mcp.shaping import DEFAULT_LIMIT, apply_limit, recommended_citation

if TYPE_CHECKING:
    from fastmcp import FastMCP


def register(mcp: FastMCP, *, service_factory: Callable[[], Any]) -> None:
    """Register the get_variant_literature tool."""

    @mcp.tool(
        name="get_variant_literature",
        title="Get Variant Literature",
        tags={"variant", "literature"},
    )
    async def get_variant_literature(
        variant_id: Annotated[str, Field(description="Variant id or RSID/HGVS.")],
        limit: Annotated[
            int,
            Field(description=f"Max publications (default {DEFAULT_LIMIT}, max 100)."),
        ] = DEFAULT_LIMIT,
    ) -> dict[str, Any] | ToolResult:
        """Return PMIDs for a variant; each row carries a recommended_citation.

        Research use only; not clinical decision support.
        """

        async def body() -> dict[str, Any]:
            if not variant_id or not variant_id.strip():
                msg = "variant_id cannot be empty"
                raise ToolValidationError(msg)
            try:
                resp = await service_factory().get_variant_literature(variant_id.strip())
            except ValidationError as exc:
                raise ToolValidationError(str(exc)) from exc
            rows = [
                {
                    "pmid": pub.pmid,
                    "recommended_citation": recommended_citation(pub.pmid),
                }
                for pub in resp.publications
                if pub.pmid
            ]
            shaped = apply_limit(rows, limit=limit)
            shaped["variant_id"] = variant_id.strip()
            shaped["cached"] = resp.cached
            return shaped

        return await run_tool("get_variant_literature", body)
