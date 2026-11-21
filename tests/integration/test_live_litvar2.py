"""Integration tests that exercise the live NCBI LitVar2 API.

These tests are excluded from the default/CI suite (the ``integration`` marker
is deselected by ``make test-unit`` / ``make test-fast`` / ``make test-cov``).
Run them explicitly with ``make test-integration`` when you need to confirm the
real upstream contract still holds. They require outbound network access and
may be rate-limited by NCBI.
"""

from __future__ import annotations

import pytest

from litvar_link.api.client import LitVar2Client
from litvar_link.config import get_api_config

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_search_variants_live() -> None:
    """A known rsID resolves to at least one variant from the live API."""
    async with LitVar2Client(get_api_config()) as client:
        results = await client.search_variants("rs1061170", limit=5)
    assert isinstance(results, list)
    assert results, "live LitVar2 search returned no variants for rs1061170"


@pytest.mark.asyncio
async def test_health_check_live() -> None:
    """The live API answers a health probe."""
    async with LitVar2Client(get_api_config()) as client:
        health = await client.health_check()
    assert isinstance(health, dict)
    assert health.get("status") in {"healthy", "unhealthy"}


@pytest.mark.asyncio
async def test_resolve_rsid_then_literature_chain_live() -> None:
    """End-to-end real API: sensor -> autocomplete enrichment -> publications,
    for CFH rs1061170 (issue #20). Excluded from ci-local; run via
    ``make test-integration``.
    """
    from litvar_link.config import get_cache_config
    from litvar_link.services.variant_service import VariantService

    async with LitVar2Client(get_api_config()) as client:
        service = VariantService(client=client, cache_config=get_cache_config())
        resolved = await service.lookup_rsid("rs1061170")
        assert resolved.available is True
        assert resolved.variant_id == "litvar@rs1061170##"
        assert resolved.gene == ["CFH"]
        assert resolved.variant_name
        lit = await service.get_variant_literature(resolved.variant_id)
        assert lit.total_count > 0
        assert all(p.pmid.isdigit() for p in lit.publications)


@pytest.mark.asyncio
async def test_versioned_transcript_hgvs_resolves_live() -> None:
    """Issue #174: LitVar2 matches transcript HGVS only with its version kept."""
    from litvar_link.config import get_cache_config
    from litvar_link.services.variant_service import VariantService

    async with LitVar2Client(get_api_config()) as client:
        service = VariantService(client=client, cache_config=get_cache_config())
        lit = await service.get_variant_literature("NM_004004.6:c.35del")
    assert lit.variant_id == "litvar@rs80338939##"
    assert lit.total_count > 0
