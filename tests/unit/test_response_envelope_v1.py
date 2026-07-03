"""Locks litvar-link's ACTUAL MCP tool boundary (``litvar_link.mcp.errors.run_tool``)
against the ratified GeneFoundry Response-Envelope Standard v1 (flat banner:
``{success, results|result, _meta(unsafe_for_clinical_use)}`` on success;
``{success: False, error_code, message, retryable, recovery_action, _meta}``
flat, in-band, on failure -- see clingen-link#20, the fleet reference).

GROUND-TRUTH FINDING -- DRIFT, NOT CONFORMANCE:
litvar-link does NOT implement the flat banner at the MCP layer at all.

  * Success: tool bodies (see e.g. ``litvar_link/mcp/tools/rsid.py``) return the
    service's plain ``model_dump()`` dict verbatim through ``run_tool`` -- there
    is no ``success`` key and no ``_meta`` key injected anywhere in
    ``litvar_link.mcp`` (confirmed by grep: no ``success``/``_meta`` handling
    exists outside this REST-only ``models/responses.py`` and
    ``logging_config.py``, neither of which touches the MCP tool boundary).
  * Errors: ``run_tool`` lets ``ToolValidationError`` propagate unchanged and
    wraps any other exception in ``ToolInternalError`` -- both are
    ``fastmcp.exceptions.ToolError`` subclasses that are *raised*, not
    returned as an in-band dict. FastMCP turns these into a protocol-level
    ``isError: true`` result; there is no flat ``{success: False, error_code,
    ...}`` dict in litvar-link's own code for the wrapper to construct.

This test therefore locks the REAL shape (exception-based, no success/_meta
banner) rather than fabricating a flat-banner contract litvar-link does not
ship. Adopting the standard here is tracked as fleet remediation work, not
fixed in this test-only PR.
"""

from __future__ import annotations

from litvar_link.mcp.errors import ToolInternalError, ToolValidationError, run_tool


async def test_success_path_has_no_success_or_meta_banner() -> None:
    """Unlike the conformant backends, a successful ``run_tool`` call returns
    the tool body's dict completely unchanged -- no ``success`` key, no
    ``_meta`` key. This is the drift this PR documents, not the target shape.
    """

    async def body() -> dict[str, object]:
        return {"id": "x"}

    result = await run_tool("resolve_rsid", body)
    assert result == {"id": "x"}
    assert "success" not in result
    assert "_meta" not in result


async def test_validation_error_propagates_unchanged_not_a_flat_error_dict() -> None:
    """A ``ToolValidationError`` raised in the body is re-raised as-is by
    ``run_tool`` -- it is never converted into an in-band
    ``{success: False, error_code, ...}`` dict.
    """

    async def body() -> dict[str, object]:
        raise ToolValidationError("bad rsid")

    try:
        await run_tool("resolve_rsid", body)
    except ToolValidationError as exc:
        assert str(exc) == "bad rsid"
    else:
        raise AssertionError("expected ToolValidationError to propagate")


async def test_unexpected_error_is_masked_into_a_raised_tool_internal_error() -> None:
    """Any other exception is sanitized into a *raised* ``ToolInternalError``
    (tool name + correlation id, no upstream detail) -- again an exception,
    not a returned flat error envelope.
    """

    async def body() -> dict[str, object]:
        raise RuntimeError("boom")

    try:
        await run_tool("resolve_rsid", body)
    except ToolInternalError as exc:
        message = str(exc)
        assert "resolve_rsid" in message
        assert "correlation_id=" in message
        assert "boom" not in message  # internal detail is not leaked
    else:
        raise AssertionError("expected ToolInternalError to propagate")
