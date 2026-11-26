"""Shared input validation for LitVar-Link (DRY cluster #1).

Single source of truth for query / limit / RSID / gene-name checks, consumed by
both ``api.client`` and ``services.variant_service``. Every failure raises
``ValidationError`` with a ``field`` so callers map it to a 400 consistently.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from litvar_link.exceptions import ForeignIdentifierError, ValidationError

MAX_QUERY_LENGTH = 100
MAX_GENE_NAME_LENGTH = 50
MIN_LIMIT = 1
MAX_LIMIT = 100
_MIN_RSID_LENGTH = 3
# ClinVar's name form NM_004004.6(GJB2):c.35del: LitVar2 matches it only without "(GJB2)".
_CLINVAR_GENE_LABEL = re.compile(r"(?<=\d)\([A-Za-z0-9-]{1,30}\)(?=:)", re.ASCII)


def safe_echo_query(query: str) -> str | None:
    """Return ``query`` if it may be repeated in a next step, else None (GTS-CORE-TXT-04).

    Allowed only at most 200 characters and free of control/format characters (Cc, Cf).
    """
    if len(query) > 200 or any(unicodedata.category(c) in ("Cc", "Cf") for c in query):
        return None
    return query


def validate_query(query: str | None) -> str:
    """Validate and normalize a free-text search query.

    Returns the stripped query. Raises ``ValidationError(field="query")``.
    A transcript HGVS keeps its version: LitVar2 matches only the versioned synonym (#174).
    """
    if not query or not query.strip():
        msg = "Query cannot be empty"
        raise ValidationError(msg, field="query")
    normalized = _CLINVAR_GENE_LABEL.sub("", query.strip(), count=1)
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


def validate_gene_name(gene_name: str | None, *, field: str = "gene_name") -> str:
    """Validate and normalize a gene symbol. Returns stripped uppercase symbol.

    A well-formed gene id from another namespace (Ensembl, HGNC, NCBI, RefSeq)
    raises ``ForeignIdentifierError``: LitVar2's gene endpoint is keyed by symbol
    only and answers such an id with an empty list.
    """
    if not gene_name or not gene_name.strip():
        msg = "Gene name cannot be empty"
        raise ValidationError(msg, field=field)
    if len(gene_name) > MAX_GENE_NAME_LENGTH:
        msg = f"Gene name too long (max {MAX_GENE_NAME_LENGTH} characters)"
        raise ValidationError(msg, field=field)
    clean = gene_name.strip().upper()
    foreign = foreign_gene_error(clean, field=field)
    if foreign:
        raise foreign
    return clean


# --- Identifiers in a namespace LitVar2 does not take (genefoundry-router #343) ---
# Converters are other fleet backends, named by their router-namespaced tool name.
# UniProt accessions are deliberately absent: their shape collides with real gene
# symbols (P2RY12), so they cannot be told apart without a lookup.
_XREF = "hgnc_resolve_gene_by_xref"
# re.ASCII everywhere: \d must not accept non-ASCII digits, since matched text is
# echoed into next_commands arguments.
_FLAGS = re.IGNORECASE | re.ASCII
_FOREIGN_GENE_FORMS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("Ensembl gene id", re.compile(r"ENSG\d{11}(\.\d+)?", _FLAGS)),
    ("Ensembl transcript id", re.compile(r"ENST\d{11}(\.\d+)?", _FLAGS)),
    ("HGNC id", re.compile(r"HGNC:\d+", _FLAGS)),
    ("RefSeq accession", re.compile(r"[NX][MRP]_\d+(\.\d+)?", _FLAGS)),
    ("NCBI Gene id", re.compile(r"(?:NCBIGENE:|GENEID:|ENTREZ:)?(\d+)", _FLAGS)),
)
_GENE_ALLOWED = ["HGNC gene symbol, e.g. KRAS"]

_CHROM_POS = r"(?:chr)?(?:[1-9]|1\d|2[0-2]|X|Y|MT?)[:\-_]\d+"
# 12-25245350-C-T, 12:25245350:C:T, chr12:25245350C>T
_COORDINATE_ALLELES = re.compile(_CHROM_POS + r"[:\-_]?[ACGTN]+[:\-_>/][ACGTN]+", _FLAGS)
# chr12:25245350, 7:100-200 -- a position or range names no variant
_COORDINATE_POSITION = re.compile(_CHROM_POS + r"(?:-\d+)?", _FLAGS)
# Printable ASCII only after ``:g.``, and capped: this text is echoed to the recoder.
_GENOMIC_HGVS = re.compile(r"NC_\d+(?:\.\d+)?:g\.[!-~]{1,200}", _FLAGS)
# NM_004004.6:c.35del, NP_000248.2:p.Lys1459Asn -- LitVar2 matches these only as
# a stored versioned synonym, so a miss says nothing about the variant (#174).
_TRANSCRIPT_HGVS = re.compile(
    r"(?:[NX][MRP]_\d+|ENST\d{11})(?:\.\d+)?(?:\([A-Za-z0-9-]{1,30}\))?:[cnp]\.[!-~]{1,200}", _FLAGS
)
_VARIANT_ALLOWED = [
    "rsID, e.g. rs1061170",
    "LitVar id, e.g. litvar@rs1061170##",
    "HGVS c./p. or protein change with its gene, e.g. BRAF V600E",
]


def foreign_gene_error(value: str, *, field: str) -> ForeignIdentifierError | None:
    """Return the ``invalid_input`` error for a gene id in a foreign namespace, else None."""
    value = value.strip()
    for form, pattern in _FOREIGN_GENE_FORMS:
        match = pattern.fullmatch(value)
        if not match:
            continue
        commands = [{"tool": "hgnc_resolve_symbol", "arguments": {"query": value}}]
        hint = "Convert the identifier to its gene symbol first, then retry with the symbol."
        if form == "NCBI Gene id":
            number = match.group(1)
            commands = [{"tool": _XREF, "arguments": {"source": "entrez_id", "value": number}}]
            if value.isdigit():  # a bare number may also be an HGNC id: offer both, guess neither
                commands.append(
                    {"tool": "hgnc_resolve_symbol", "arguments": {"query": f"HGNC:{number}"}}
                )
        elif form == "Ensembl transcript id":
            # No fleet converter is guaranteed for an arbitrary transcript: name none.
            commands = []
            hint = "This is a transcript id; this tool takes the gene's HGNC symbol instead."
        return ForeignIdentifierError(
            f"{field} is not a gene symbol (shape: {form}). LitVar2 is keyed by gene symbol "
            "and cannot look that up, so this says nothing about the gene's variants.",
            field=field,
            allowed_values=_GENE_ALLOWED,
            hint=hint,
            next_commands=commands,
        )
    return None


def genomic_variant_error(
    value: str, *, field: str = "variant_id", coordinates_only: bool = False
) -> ForeignIdentifierError | None:
    """Return the ``invalid_input`` error for a genomic coordinate / g. HGVS, else None.

    LitVar2 indexes variants by rsID and by gene-anchored HGVS; it has no position
    lookup. Only an ``NC_...:g.`` HGVS gets a converter call (vep-link's recoder reads
    rsID, HGVS and SPDI): no fleet tool is verified to turn CHR-POS-REF-ALT into an
    rsID, and a position or range without alleles names no variant at all.

    A transcript HGVS LitVar2 did not match gets the same converter call (#174).

    ``coordinates_only`` skips genomic and transcript HGVS: the service lets LitVar2
    try those first, and the MCP tools call this again with the caller's own (still versioned) text
    once LitVar2 has not resolved it.
    """
    value = value.strip()
    commands: list[dict[str, Any]] = []
    why = "LitVar2 has no position lookup"
    if _COORDINATE_ALLELES.fullmatch(value):
        what = "a genomic coordinate"
        hint = "LitVar2 needs the variant's rsID or HGVS; look it up and retry with that."
    elif _COORDINATE_POSITION.fullmatch(value):
        what = "a genomic position or range without alleles, which names no variant"
        hint = "Give the variant itself as an rsID or HGVS; a position alone is not enough."
    elif not coordinates_only and _GENOMIC_HGVS.fullmatch(value):
        what = "a genomic (g.) HGVS"
        hint = "Convert it to an rsID or a c./p. HGVS first, then retry with that."
        commands = [{"tool": "vep_recode_variant", "arguments": {"variants": [value]}}]
    elif not coordinates_only and _TRANSCRIPT_HGVS.fullmatch(value):
        what = "a transcript HGVS"
        why = "LitVar2 matched no stored synonym for it"
        hint = "Convert it to an rsID first, then retry with the rsID."
        commands = [{"tool": "vep_recode_variant", "arguments": {"variants": [value]}}]
    else:
        return None
    return ForeignIdentifierError(
        f"{field} looks like {what}; {why}, so this says "
        "nothing about whether the variant has literature.",
        field=field,
        allowed_values=_VARIANT_ALLOWED,
        hint=hint,
        next_commands=commands,
    )
