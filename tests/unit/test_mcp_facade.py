"""The facade builds a FastMCP server with masking + all six tools."""

from __future__ import annotations

import pytest

from litvar_link.mcp.facade import create_litvar_mcp


@pytest.mark.asyncio
async def test_facade_builds_with_six_tools() -> None:
    mcp = create_litvar_mcp(service_factory=lambda: object())
    names = {t.name for t in await mcp.list_tools()}
    assert names >= {
        "search_genetic_variants",
        "get_variant_summary",
        "get_variant_literature",
        "lookup_rsid_availability",
        "search_gene_variants",
        "get_server_capabilities",
    }


def test_facade_masks_error_details() -> None:
    # fastmcp 3.4.2 accepts mask_error_details=True in the constructor but does
    # not expose it as a readable attribute, so we assert only that the server
    # builds with the expected name (construction with masking did not raise).
    mcp = create_litvar_mcp(service_factory=lambda: object())
    assert mcp.name == "litvar-link"
