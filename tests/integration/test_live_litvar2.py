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
