"""Locks litvar-link's MCP tool boundary (``litvar_link.mcp.errors.run_tool``)
against the ratified GeneFoundry Response-Envelope Standard v1 (flat banner:
``{success, results|result, _meta(unsafe_for_clinical_use)}`` on success;
``{success: False, error_code, message, retryable, recovery_action, _meta}``
flat, in-band, on failure -- see clingen-link#20, the fleet reference).

CONFORMANCE, NOT DRIFT (as of the v3.0.0 envelope migration):
litvar-link now implements the flat banner at the MCP layer.

  * Success: ``run_tool`` banner-wraps the tool body's returned dict with
    ``success: True`` and merges a provenance ``_meta`` block (``tool``,
    ``request_id``, ``elapsed_ms``, ``source``, ``unsafe_for_clinical_use``)
    around whatever the body returned -- payload-shape-agnostic, matching the
    fleet reference (clingen-link's ``run_mcp_tool``).
  * Errors: ``run_tool`` NEVER lets an exception propagate. It classifies the
    exception into the closed ``error_code`` enum and RETURNS a flat in-band
    envelope wrapped in a ``fastmcp.tools.tool.ToolResult(is_error=True)`` --
    verified against the installed fastmcp 3.4.2 API (``ToolResult`` accepts
    ``structured_content`` + ``is_error``; a tool function returning a
    ``ToolResult`` is passed through unchanged by ``Tool.convert_result``), so
    both the in-band dict AND the wire ``CallToolResult.isError`` are set.

This test is the CI regression gate for that contract at the wrapper boundary,
adapted from the fleet-reference locking test in clingen-link.
"""

from __future__ import annotations

from typing import Any

from fastmcp.tools.tool import ToolResult

from litvar_link.mcp.errors import ToolValidationError, run_tool


async def test_success_envelope_matches_response_envelope_standard_v1() -> None:
    """A dict-returning tool body is banner-wrapped: success + payload + _meta.

    Uses the fleet-canon ``results`` payload key (array of records); the
    wrapper is payload-shape-agnostic and merges the banner around whatever
    the tool body returns, so this also covers the single-item ``result``
    (object) variant below.
    """

    async def body() -> dict[str, Any]:
        return {"results": [{"rsid": "rs1061170"}]}

    result = await run_tool("search_genetic_variants", body)

    assert isinstance(result, dict)
    assert result["success"] is True
    assert result["results"] == [{"rsid": "rs1061170"}]
    assert result["_meta"]["tool"] == "search_genetic_variants"
    assert result["_meta"]["unsafe_for_clinical_use"] is True
    assert isinstance(result["_meta"]["request_id"], str) and result["_meta"]["request_id"]
    assert isinstance(result["_meta"]["elapsed_ms"], int)


async def test_single_item_result_key_is_preserved() -> None:
    """The single-item ``result`` (object) payload variant is passed through unchanged."""

    async def body() -> dict[str, Any]:
        return {"result": {"rsid": "rs1061170", "available": True}}

    result = await run_tool("resolve_rsid", body)

    assert isinstance(result, dict)
    assert result["success"] is True
    assert result["result"] == {"rsid": "rs1061170", "available": True}
    assert result["_meta"]["unsafe_for_clinical_use"] is True


async def test_error_envelope_is_flat_and_returned_not_raised() -> None:
    """A ``ToolValidationError`` raised in the body is classified and RETURNED
    as a flat in-band envelope -- never a bare/propagating exception, and never
    the strict nested ``error: {code, message, retriable, details}`` shape.
    """

    async def body() -> dict[str, Any]:
        raise ToolValidationError("bad rsid")

    result = await run_tool("resolve_rsid", body)

    assert isinstance(result, ToolResult)
    assert result.is_error is True
    payload = result.structured_content or {}
    assert payload["success"] is False
    assert payload["error_code"] == "invalid_input"
    assert payload["message"] == "bad rsid"
    assert payload["retryable"] is False
    assert isinstance(payload["recovery_action"], str) and payload["recovery_action"]
    # Flat, not nested: no strict-Rules "error" object anywhere in the payload.
    assert "error" not in payload
    assert payload["_meta"]["tool"] == "resolve_rsid"
    assert payload["_meta"]["unsafe_for_clinical_use"] is True


async def test_unexpected_error_is_returned_as_a_masked_internal_envelope() -> None:
    """Any other exception is classified ``internal`` and its detail is
    sanitized out of the in-band ``message`` (tool name + request id only, no
    upstream/implementation detail) -- again returned, never raised.
    """

    async def body() -> dict[str, Any]:
        raise RuntimeError("boom")

    result = await run_tool("resolve_rsid", body)

    assert isinstance(result, ToolResult)
    assert result.is_error is True
    payload = result.structured_content or {}
    assert payload["success"] is False
    assert payload["error_code"] == "internal"
    assert payload["retryable"] is False
    assert "resolve_rsid" in payload["message"]
    assert "request_id=" in payload["message"]
    assert "boom" not in payload["message"]  # internal detail is not leaked
    assert payload["_meta"]["request_id"] in payload["message"]
