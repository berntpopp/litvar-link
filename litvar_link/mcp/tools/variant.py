"""MCP tool: get_variant_summary."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Annotated, Any, Literal

from pydantic import Field

from litvar_link.exceptions import ValidationError
from litvar_link.mcp.errors import ToolValidationError, run_tool

if TYPE_CHECKING:
    from fastmcp import FastMCP

_COMPACT_FIELDS = ("id", "rsid", "gene", "name", "pmids_count")


def register(mcp: FastMCP, *, service_factory: Callable[[], Any]) -> None:
    """Register the get_variant_summary tool."""

    @mcp.tool(name="get_variant_summary", title="Get Variant Summary")
    async def get_variant_summary(
        variant_id: Annotated[str, Field(description="LitVar2 variant id or RSID/HGVS.")],
        response_mode: Annotated[
            Literal["compact", "full"],
            Field(description="compact or full payload."),
        ] = "compact",
    ) -> dict[str, Any]:
        """Return details for a known variant id. Research use only."""

        async def body() -> dict[str, Any]:
            if not variant_id or not variant_id.strip():
                msg = "variant_id cannot be empty"
                raise ToolValidationError(msg)
            try:
                resp = await service_factory().get_variant_summary(variant_id.strip())
            except ValidationError as exc:
                raise ToolValidationError(str(exc)) from exc
            data: dict[str, Any] = resp.model_dump()
            if response_mode == "compact":
                variant = data.get("variant") or {}
                data["variant"] = {k: variant[k] for k in _COMPACT_FIELDS if k in variant}
            return data

        return await run_tool("get_variant_summary", body)
