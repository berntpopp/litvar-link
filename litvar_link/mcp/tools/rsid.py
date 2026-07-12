"""MCP tool: resolve_rsid."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Annotated, Any

from fastmcp.tools.tool import ToolResult
from pydantic import Field

from litvar_link.exceptions import ValidationError
from litvar_link.mcp.annotations import READ_ONLY_OPEN_WORLD
from litvar_link.mcp.errors import ToolValidationError, run_tool
from litvar_link.validation import validate_rsid

if TYPE_CHECKING:
    from fastmcp import FastMCP

# The resolved rsID record is wrapped under ``result`` (structured, no free text).
RESOLVE_RSID_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"result": {"type": "object", "additionalProperties": True}},
    "required": ["result"],
    "additionalProperties": True,
}


def register(mcp: FastMCP, *, service_factory: Callable[[], Any]) -> None:
    """Register the resolve_rsid tool."""

    @mcp.tool(
        name="resolve_rsid",
        title="Resolve RSID",
        tags={"variant"},
        output_schema=RESOLVE_RSID_OUTPUT_SCHEMA,
        annotations=READ_ONLY_OPEN_WORLD,
    )
    async def resolve_rsid(
        variant_id: Annotated[str, Field(description="dbSNP rsID, e.g. rs1061170.")],
    ) -> dict[str, Any] | ToolResult:
        """Resolve an rsID to its existence/record in LitVar2. Research use only."""

        async def body() -> dict[str, Any]:
            try:
                clean = validate_rsid(variant_id)
            except ValidationError as exc:
                raise ToolValidationError(str(exc)) from exc
            resp = await service_factory().lookup_rsid(clean)
            data: dict[str, Any] = resp.model_dump()
            return {"result": data}

        return await run_tool("resolve_rsid", body)
