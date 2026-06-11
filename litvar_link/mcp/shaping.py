"""Response shaping for MCP tools: compact/full modes, limits, citations."""

from __future__ import annotations

from typing import Any, Literal

ResponseMode = Literal["compact", "full"]

DEFAULT_LIMIT = 25
MAX_LIMIT = 100

# Fields kept in compact variant rows (high-signal only).
_COMPACT_VARIANT_FIELDS = ("_id", "id", "rsid", "gene", "name", "pmids_count")


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


def shape_variant_row(row: dict[str, Any], *, mode: ResponseMode) -> dict[str, Any]:
    """Project a variant row for the requested response mode.

    ``full`` returns the row unchanged; ``compact`` keeps only high-signal fields.
    """
    if mode == "full":
        return row
    return {k: row[k] for k in _COMPACT_VARIANT_FIELDS if k in row}


def recommended_citation(pmid: str) -> str:
    """Return a PMID-based citation string clients paste verbatim."""
    return f"PMID:{pmid}. https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
