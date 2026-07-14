"""Response shaping for MCP tools: compact/full modes, limits, citations."""

from __future__ import annotations

import base64
from typing import Any, Literal

from litvar_link.exceptions import ValidationError
from litvar_link.mcp.untrusted_content import UntrustedText, fence_untrusted_text

ResponseMode = Literal["compact", "full"]

DEFAULT_LIMIT = 25
MAX_LIMIT = 100

# Opaque, stateless cursor: base64url("o:<offset>"). Opaque so the wire format
# stays ours to change; stateless so no server-side page state can expire.
_CURSOR_PREFIX = "o:"

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


def encode_cursor(offset: int) -> str:
    """Encode a row offset as an opaque, stateless pagination cursor."""
    raw = f"{_CURSOR_PREFIX}{offset}".encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str | None) -> int:
    """Decode an opaque cursor to a row offset. ``None``/empty means "first page".

    An invalid or corrupt cursor is an EXECUTION ERROR, never a silent first page
    (Response-Envelope Standard v1 §5): silently restarting at row 0 would make a
    paging agent loop forever over the same page and believe it was advancing.
    """
    if not cursor:
        return 0
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        raw = base64.urlsafe_b64decode(padded.encode()).decode()
    except (ValueError, UnicodeDecodeError) as exc:
        msg = "Invalid cursor. Omit `cursor` to start from the first page."
        raise ValidationError(msg, field="cursor") from exc
    if not raw.startswith(_CURSOR_PREFIX):
        msg = "Invalid cursor. Omit `cursor` to start from the first page."
        raise ValidationError(msg, field="cursor")
    try:
        offset = int(raw[len(_CURSOR_PREFIX) :])
    except ValueError as exc:
        msg = "Invalid cursor. Omit `cursor` to start from the first page."
        raise ValidationError(msg, field="cursor") from exc
    if offset < 0:
        msg = "Invalid cursor. Omit `cursor` to start from the first page."
        raise ValidationError(msg, field="cursor")
    return offset


def paginate(
    rows: list[Any],
    *,
    limit: int,
    offset: int = 0,
    total_count: int | None,
    has_more: bool | None = None,
    cursors: bool = True,
) -> dict[str, Any]:
    """Slice ``rows`` into a page and emit an HONEST `_meta.pagination` block.

    Replaces the old ``apply_limit``, which set ``total = len(rows)`` -- i.e. the
    PAGE SIZE -- so ``truncated`` could never be true. An agent read
    ``returned:25, total:25, truncated:false`` and concluded it had seen every
    BRCA1 variant LitVar knows; it had seen 0.2% of them (issue #66 D2).

    ``total_count`` is the REAL upstream total, or ``None`` where the upstream
    genuinely supplies no count (LitVar's autocomplete). ``None`` is the honest
    answer -- inventing a number is what caused the defect. ``has_more`` may be
    passed explicitly where the caller knows it better than this slice does
    (e.g. an over-fetched suggest page).
    """
    capped = max(1, min(limit, MAX_LIMIT))
    sliced = rows[offset : offset + capped]
    if has_more is None:
        has_more = (offset + len(sliced)) < len(rows)
    next_cursor = encode_cursor(offset + len(sliced)) if (cursors and has_more and sliced) else None
    return {
        "results": sliced,
        "returned": len(sliced),
        "_meta": {
            "pagination": {
                "total_count": total_count,
                "has_more": has_more,
                "next_cursor": next_cursor,
            }
        },
    }


def fence_match_field(row: dict[str, Any]) -> dict[str, Any]:
    """Fence a row's upstream ``match`` HTML search-snippet as ``untrusted_text``.

    A no-op copy when ``match`` is absent or ``None`` (the declared schema
    permits ``null``). Any ``str`` value -- INCLUDING the empty string -- is
    fenced into the typed object, so a present ``match`` is *always* the
    ``untrusted_text`` object on the wire and never a bare string: emitting a
    bare ``""`` would contradict the declared ``anyOf[null, UntrustedText]``
    schema and be skipped by the limit collector. The fenced object is an
    OPAQUE typed leaf: no sibling field duplicates the raw or cleaned prose,
    and the fence does not strip HTML markup (a presentation concern, not a
    security boundary) -- only control/zero-width/bidi code points are removed.
    """
    match = row.get("match")
    if not isinstance(match, str):
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
