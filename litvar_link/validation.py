"""Shared input validation for LitVar-Link (DRY cluster #1).

Single source of truth for query / limit / RSID / gene-name checks, consumed by
both ``api.client`` and ``services.variant_service``. Every failure raises
``ValidationError`` with a ``field`` so callers map it to a 400 consistently.
"""

from __future__ import annotations

import re

from litvar_link.exceptions import ValidationError

MAX_QUERY_LENGTH = 100
MAX_GENE_NAME_LENGTH = 50
MIN_LIMIT = 1
MAX_LIMIT = 100
_MIN_RSID_LENGTH = 3

_HGVS_VERSION_PATTERN = re.compile(r"\b([A-Za-z]{2,}_[0-9]+|ENS[A-Z]+[0-9]+)\.[0-9]+(?=:|\b)")


def normalize_hgvs(text: str) -> str:
    """Normalize HGVS notation by stripping transcript version decimals.

    NCBI LitVar2 autocomplete/search does not match versioned RefSeq transcript
    accessions (e.g. 'NM_001458.5:c.6651del' or 'NM_001458.5'), but succeeds when
    queried with unversioned accessions ('NM_001458:c.6651del' or 'NM_001458').
    """
    if not text:
        return text
    return _HGVS_VERSION_PATTERN.sub(r"\1", text)


def validate_query(query: str | None) -> str:
    """Validate and normalize a free-text search query.

    Returns the stripped and HGVS-normalized query. Raises ``ValidationError(field="query")``.
    """
    if not query or not query.strip():
        msg = "Query cannot be empty"
        raise ValidationError(msg, field="query")
    normalized = normalize_hgvs(query.strip())
    if len(normalized) > MAX_QUERY_LENGTH:
        msg = f"Query too long (max {MAX_QUERY_LENGTH} characters)"
        raise ValidationError(msg, field="query")
    return normalized


def validate_limit(limit: int) -> int:
    """Validate a result limit is within ``[MIN_LIMIT, MAX_LIMIT]``."""
    if not MIN_LIMIT <= limit <= MAX_LIMIT:
        msg = f"Limit must be between {MIN_LIMIT} and {MAX_LIMIT}"
        raise ValidationError(msg, field="limit")
    return limit


def validate_rsid(rsid: str | None) -> str:
    """Validate and normalize an RSID. Returns lowercased ``rs<digits>``."""
    if not rsid or not rsid.strip():
        msg = "RSID cannot be empty"
        raise ValidationError(msg, field="rsid")
    normalized = rsid.strip().lower()
    if (
        len(normalized) < _MIN_RSID_LENGTH
        or not normalized.startswith("rs")
        or not normalized[2:].isdigit()
    ):
        msg = "Invalid RSID format (should be 'rs' followed by digits)"
        raise ValidationError(msg, field="rsid")
    return normalized


def validate_gene_name(gene_name: str | None) -> str:
    """Validate and normalize a gene symbol. Returns stripped uppercase symbol."""
    if not gene_name or not gene_name.strip():
        msg = "Gene name cannot be empty"
        raise ValidationError(msg, field="gene_name")
    if len(gene_name) > MAX_GENE_NAME_LENGTH:
        msg = f"Gene name too long (max {MAX_GENE_NAME_LENGTH} characters)"
        raise ValidationError(msg, field="gene_name")
    return gene_name.strip().upper()
