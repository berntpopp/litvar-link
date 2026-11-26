"""Response-Envelope Standard v1.2: every data tool's result validates against the
published JSON Schema and names its provenance."""

from __future__ import annotations

import hashlib
import json
from typing import Any

import jsonschema
import pytest
from fastmcp import FastMCP

from litvar_link.config import CacheConfig
from litvar_link.mcp.facade import create_litvar_mcp
from litvar_link.services.variant_service import VariantService
from tests.conformance.envelope_schema import SCHEMA, SCHEMA_FILE, assert_data_envelope

# Orient a client and return no upstream data: outside the v1.2 provenance rule.
OPS_TOOLS = {"get_server_capabilities"}


@pytest.fixture
def mcp(
    mock_litvar_client: Any,
    sample_variant_data: dict[str, Any],
    sample_gene_variants_data: list[dict[str, Any]],
    sample_sensor_data: dict[str, Any],
    sample_publication_data: list[str],
) -> FastMCP:
    """The real server over the real service and cache, with a canned LitVar2 client."""
    mock_litvar_client.search_variants.return_value = [sample_variant_data]
    mock_litvar_client.get_variant_details.return_value = sample_variant_data
    mock_litvar_client.get_variant_publications.return_value = sample_publication_data
    mock_litvar_client.sensor_lookup.return_value = sample_sensor_data
    mock_litvar_client.get_variants_by_gene.return_value = sample_gene_variants_data
    service = VariantService(mock_litvar_client, CacheConfig())
    return create_litvar_mcp(service_factory=lambda: service)


async def _call(mcp: FastMCP, name: str) -> dict[str, Any]:
    tool = await mcp.get_tool(name)
    props = tool.parameters.get("properties", {})
    args = {k: props[k]["examples"][0] for k in tool.parameters.get("required", [])}
    result = await mcp.call_tool(name, args)
    envelope = result.structured_content
    assert envelope is not None, name
    assert json.loads(result.content[0].text) == envelope, name
    return envelope


def test_vendored_schema_matches_pinned_sha256() -> None:
    pinned = SCHEMA_FILE.with_suffix(".sha256").read_text().split()[0]
    assert hashlib.sha256(SCHEMA_FILE.read_bytes()).hexdigest() == pinned


async def test_every_data_tool_result_validates_and_carries_provenance(mcp: FastMCP) -> None:
    names = [t.name for t in await mcp.list_tools() if t.name not in OPS_TOOLS]
    assert len(names) == 5
    for name in names:
        envelope = await _call(mcp, name)
        try:
            assert_data_envelope(envelope)
        except (AssertionError, jsonschema.ValidationError) as exc:
            raise AssertionError(f"{name}: {exc}") from exc
        assert envelope["_meta"]["source"] == "litvar"
        assert envelope["_meta"]["data_version"] == "live"


async def test_cache_hit_keeps_the_original_retrieved_at(
    mcp: FastMCP, mock_litvar_client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """v1.2: a cached result reports the fetch that filled the entry, not the read."""
    from datetime import UTC, datetime

    from litvar_link import provenance
    from litvar_link.utils import caching

    class _Clock(datetime):
        current = datetime(2026, 1, 1, 8, 0, 0, tzinfo=UTC)

        @classmethod
        def now(cls, tz: Any = None) -> datetime:
            return cls.current

    monkeypatch.setattr(caching, "datetime", _Clock)
    monkeypatch.setattr(provenance, "datetime", _Clock)
    first = await _call(mcp, "search_gene_variants")
    _Clock.current = datetime(2026, 1, 1, 9, 0, 0, tzinfo=UTC)
    second = await _call(mcp, "search_gene_variants")
    assert mock_litvar_client.get_variants_by_gene.await_count == 1
    assert first["_meta"]["retrieved_at"] == "2026-01-01T08:00:00Z"
    assert second["_meta"]["retrieved_at"] == "2026-01-01T08:00:00Z"


async def test_error_envelope_validates_against_schema(mcp: FastMCP) -> None:
    result = await mcp.call_tool("resolve_rsid", {"rsid": "not-an-rsid"})
    assert result.structured_content["success"] is False
    jsonschema.validate(result.structured_content, SCHEMA)
