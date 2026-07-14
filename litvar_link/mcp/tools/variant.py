"""MCP tool: get_variant_summary."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Annotated, Any, Literal

from fastmcp.tools.tool import ToolResult
from pydantic import Field

from litvar_link.exceptions import ValidationError
from litvar_link.mcp.annotations import READ_ONLY_OPEN_WORLD
from litvar_link.mcp.errors import ToolValidationError, run_tool
from litvar_link.mcp.shaping import (
    collect_fenced_matches,
    fence_match_field,
)
from litvar_link.mcp.untrusted_content import enforce_untrusted_text_limits

if TYPE_CHECKING:
    from fastmcp import FastMCP

# High-signal fields for compact mode. Includes the clinically meaningful ones a
# curator actually asks this tool for (ClinGen ids, genomic position, reported
# significance) -- the old projection dropped all three.
_COMPACT_FIELDS = (
    "id",
    "rsid",
    "gene",
    "name",
    "hgvs",
    "pmids_count",
    "clingen_ids",
    "data_chromosome_base_position",
    "data_clinical_significance",
)


# Parameter types hoisted to module level: the tool signature stays inside the
# per-function LOC budget WITHOUT shortening a single description (descriptions
# are what the model reads -- TOOL-SCHEMA-DOCUMENTATION-STANDARD S1/S6).
VariantIdParam = Annotated[
    str,
    Field(
        description=(
            "LitVar2 variant id (litvar@rs...##), rsID, or HGVS/protein name. "
            "Non-canonical input is resolved via autocomplete; the record that "
            "actually answered is echoed back as `resolved_variant_id`."
        ),
        examples=["litvar@rs1061170##", "rs1061170"],
    ),
]
ResponseModeParam = Annotated[
    Literal["compact", "full"],
    Field(description="compact (high-signal fields) or full (raw payload)."),
]


def register(mcp: FastMCP, *, service_factory: Callable[[], Any]) -> None:
    """Register the get_variant_summary tool."""

    @mcp.tool(
        name="get_variant_summary",
        title="Get Variant Summary",
        tags={"variant"},
        output_schema=None,  # Tool-Surface Budget v1 B3: structuredContent is unaffected.
        annotations=READ_ONLY_OPEN_WORLD,
    )
    async def get_variant_summary(
        variant_id: VariantIdParam,
        response_mode: ResponseModeParam = "compact",
    ) -> dict[str, Any] | ToolResult:
        """Return the LitVar2 record for a variant: gene, name, HGVS, ClinGen ids,
        genomic position and the clinical significances LitVar2 reports for it.

        Accepts a canonical LitVar id, an rsID, or HGVS/protein notation.

        Research use only; not clinical decision support.
        """

        async def body() -> dict[str, Any]:
            if not variant_id or not variant_id.strip():
                msg = "variant_id cannot be empty"
                raise ToolValidationError(msg)
            try:
                resp = await service_factory().get_variant_summary(variant_id.strip())
            except ValidationError as exc:
                raise ToolValidationError(str(exc)) from exc
            data: dict[str, Any] = resp.model_dump()
            variant = data.get("variant") or {}
            if response_mode == "compact":
                variant = {k: variant[k] for k in _COMPACT_FIELDS if k in variant}
            else:
                variant = fence_match_field(variant)
                # Single-record tool: the default 128-object ceiling bounds
                # this (at most one fenced field), per the fleet convention.
                enforce_untrusted_text_limits(collect_fenced_matches([variant]))
            return {
                "result": variant,
                # Free text / an rsID is resolved via autocomplete, so the caller
                # MUST be told which LitVar record actually answered.
                "resolved_variant_id": data.get("resolved_variant_id"),
                "cached": data.get("cached", False),
            }

        return await run_tool("get_variant_summary", body)
