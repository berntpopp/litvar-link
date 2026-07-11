"""Response shaping for MCP tools: compact/full modes, limits, citations."""

from __future__ import annotations

from typing import Any, Literal

from litvar_link.mcp.untrusted_content import UntrustedText, fence_untrusted_text

ResponseMode = Literal["compact", "full"]

DEFAULT_LIMIT = 25
MAX_LIMIT = 100

# Fields kept in compact variant rows (high-signal only).
_COMPACT_VARIANT_FIELDS = ("_id", "id", "rsid", "gene", "name", "pmids_count")

# Full-mode-only field carrying an upstream free-text search snippet with HTML
# highlighting (``Variant.match`` / ``AutocompleteVariantItem.match``, both in
# ``litvar_link/models/``). Compact mode never surfaces it. Reachable from two
# tools that share this row shape: ``search_genetic_variants`` (list of rows,
# via ``shape_variant_row``) and ``get_variant_summary`` (one row, via
# ``fence_match_field`` directly -- ``VariantDetails`` inherits ``match`` from
# ``Variant`` even though the "variant details" upstream endpoint does not
# normally populate it; fenced defensively so an unexpected non-null value is
# never passed through unfenced).
_UNTRUSTED_TEXT_SOURCE = "litvar"


def apply_limit(rows: list[Any], *, limit: int) -> dict[str, Any]:
    """Truncate ``rows`` to ``limit`` with explicit truncation markers.

    Returns ``{results, returned, total, truncated}`` rather than silently
    dropping rows (per Anthropic tool-design guidance).
    """
    capped = max(1, min(limit, MAX_LIMIT))
    sliced = rows[:capped]
    return {
        "results": sliced,
        "returned": len(sliced),
        "total": len(rows),
        "truncated": len(rows) > len(sliced),
    }


def fence_match_field(row: dict[str, Any]) -> dict[str, Any]:
    """Fence a row's upstream ``match`` HTML search-snippet as ``untrusted_text``.

    A no-op copy when ``match`` is absent/``None``/empty -- the field is
    optional and most rows never populate it. The fenced object is an OPAQUE
    typed leaf: no sibling field duplicates the raw or cleaned prose, and the
    fence does not strip HTML markup (a presentation concern, not a security
    boundary) -- only control/zero-width/bidi code points are removed.
    """
    match = row.get("match")
    if not isinstance(match, str) or not match:
        return dict(row)
    shaped = dict(row)
    variant_id = str(row.get("id") or row.get("_id") or row.get("rsid") or "unknown")
    fenced = fence_untrusted_text(match, source=_UNTRUSTED_TEXT_SOURCE, record_id=variant_id)
    shaped["match"] = fenced.model_dump(mode="json")
    return shaped


def collect_fenced_matches(rows: list[dict[str, Any]]) -> list[UntrustedText]:
    """Reconstruct every fenced ``match`` object across a set of rows.

    Used to aggregate ALL fenced objects a response emits -- across every row,
    not per-record -- into one ``enforce_untrusted_text_limits`` call, so the
    object-count/byte-size ceilings bound the actual response payload.
    """
    return [
        UntrustedText.model_validate(row["match"])
        for row in rows
        if isinstance(row.get("match"), dict)
    ]


def untrusted_text_field_schema() -> tuple[dict[str, Any], dict[str, Any]]:
    """Return ``(field_schema, defs)`` for an optional ``UntrustedText`` field.

    ``field_schema`` is a ``$defs``-free fragment (the ``kind`` const lives at
    ``field_schema["anyOf"][1]["properties"]["kind"]``) suitable for embedding
    directly into a tool's ``output_schema`` array-item or object properties;
    ``defs`` MUST be merged into that schema document's top-level ``$defs`` so
    the embedded ``$ref``s resolve.
    """
    schema = UntrustedText.model_json_schema()
    defs = schema.pop("$defs", {})
    return {"anyOf": [{"type": "null"}, schema]}, defs


def shape_variant_row(row: dict[str, Any], *, mode: ResponseMode) -> dict[str, Any]:
    """Project a variant row for the requested response mode.

    ``full`` returns the row with its upstream free-text ``match`` snippet
    fenced as a typed ``untrusted_text`` object (Response-Envelope v1.1);
    ``compact`` keeps only high-signal fields and never surfaces ``match`` at
    all -- the fence is not needed there because the field is absent.
    """
    if mode == "full":
        return fence_match_field(row)
    return {k: row[k] for k in _COMPACT_VARIANT_FIELDS if k in row}


def recommended_citation(pmid: str) -> str:
    """Return a PMID-based citation string clients paste verbatim."""
    return f"PMID:{pmid}. https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
