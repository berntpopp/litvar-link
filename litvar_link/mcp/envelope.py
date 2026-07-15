"""Flat-banner envelope shape for the ratified GeneFoundry Response-Envelope
Standard v1 (see ``docs/RESPONSE-ENVELOPE-STANDARD-v1.md`` in the
``genefoundry-router`` repo; OQ4 resolved -> Option A, the flat banner).

Pure, side-effect-free shape helpers. ``litvar_link.mcp.errors.run_tool`` is the
boundary that calls these; keeping the shaping logic here (mirroring
clingen-link's ``mcp/envelope.py``) keeps that module focused on classification
and control flow.

- SUCCESS: ``{"success": True, <tool payload>, "_meta": {tool, request_id,
  elapsed_ms, source, unsafe_for_clinical_use}}``.
- FAILURE: a FLAT (never nested) ``{"success": False, "error_code", "message",
  "retryable", "recovery_action", "_meta": {...}}``.

Every tool body decides its own primary payload key -- ``results`` (array) for
collections, ``result`` (object) for single-item lookups -- per Rules §1; the
envelope only injects ``success``/``_meta`` around whatever the body returns.
"""

from __future__ import annotations

from typing import Any, Literal

SOURCE_NAME = "litvar-link"

# THE closed error-code enum (Response-Envelope Standard v1 Rules §2). Exactly
# these six, and nothing else -- a client branching on error_code cannot handle a
# code it has never heard of. litvar-link previously also shipped
# ``response_limit_exceeded``; however sensible it read, it was outside the enum,
# so it is now mapped onto ``invalid_input`` (the caller's fix is the same: lower
# `limit` and retry).
ErrorCode = Literal[
    "invalid_input",
    "not_found",
    "ambiguous_query",
    "upstream_unavailable",
    "rate_limited",
    "internal",
]

# Merged into every envelope's ``_meta`` block, success and error alike.
_BASE_META: dict[str, Any] = {"unsafe_for_clinical_use": True}


def provenance_meta(
    *,
    tool_name: str | None,
    request_id: str,
    elapsed_ms: int,
) -> dict[str, Any]:
    """Build the envelope ``_meta`` provenance block (Rules §4: MUST fields).

    ``tool_name`` is ``str | None``: the FastMCP-core not-found guard builds a
    fixed, name-free error envelope for an unknown tool with ``tool_name=None`` so
    the caller-supplied (untrusted) requested name is never reflected back into
    ``_meta.tool``.
    """
    return {
        "tool": tool_name,
        "request_id": request_id,
        "elapsed_ms": elapsed_ms,
        "source": SOURCE_NAME,
        **_BASE_META,
    }


def success_envelope(
    data: dict[str, Any],
    *,
    tool_name: str,
    request_id: str,
    elapsed_ms: int,
) -> dict[str, Any]:
    """Wrap a tool body's payload dict in the flat success banner.

    Any ``_meta`` the body already set is preserved and merged under (not
    replaced by) the provenance block, so a future tool can add domain-specific
    meta fields (e.g. pagination) without losing the mandatory ones.
    """
    body_meta = data.get("_meta")
    existing_meta: dict[str, Any] = dict(body_meta) if isinstance(body_meta, dict) else {}
    envelope: dict[str, Any] = {"success": True}
    envelope.update({key: value for key, value in data.items() if key != "_meta"})
    envelope["_meta"] = {
        **existing_meta,
        **provenance_meta(
            tool_name=tool_name,
            request_id=request_id,
            elapsed_ms=elapsed_ms,
        ),
    }
    return envelope


def error_envelope(
    *,
    tool_name: str | None,
    request_id: str,
    elapsed_ms: int,
    error_code: ErrorCode,
    message: str,
    retryable: bool,
    recovery_action: str,
) -> dict[str, Any]:
    """Build the flat, in-band execution-error frame (Rules §2)."""
    return {
        "success": False,
        "error_code": error_code,
        "message": message,
        "retryable": retryable,
        "recovery_action": recovery_action,
        "_meta": provenance_meta(
            tool_name=tool_name,
            request_id=request_id,
            elapsed_ms=elapsed_ms,
        ),
    }
