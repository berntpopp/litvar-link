"""MCP tool: lookup_rsid_availability."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Annotated, Any

from pydantic import Field

from litvar_link.exceptions import ValidationError
from litvar_link.mcp.errors import ToolValidationError, run_tool
from litvar_link.validation import validate_rsid

if TYPE_CHECKING:
    from fastmcp import FastMCP


def register(mcp: FastMCP, *, service_factory: Callable[[], Any]) -> None:
    """Register the lookup_rsid_availability tool."""

    @mcp.tool(name="lookup_rsid_availability", title="Lookup RSID Availability")
    async def lookup_rsid_availability(
        rsid: Annotated[str, Field(description="dbSNP RSID, e.g. rs1061170.")],
    ) -> dict[str, Any]:
        """Check whether an rsID exists in LitVar2. Research use only."""

        async def body() -> dict[str, Any]:
            try:
                clean = validate_rsid(rsid)
            except ValidationError as exc:
                raise ToolValidationError(str(exc)) from exc
            resp = await service_factory().lookup_rsid(clean)
            return resp.model_dump()

        return await run_tool("lookup_rsid_availability", body)
