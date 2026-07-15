"""What a canonical LitVar2 variant id is, and which upstream 4xx means "no such variant"."""

from __future__ import annotations

from litvar_link.exceptions import LitVarAPIError

# Canonical LitVar variant ids look like "litvar@rs113993960##". The publications
# endpoint only accepts this form, so non-canonical input (rsID/HGVS/free text)
# must be resolved via autocomplete first.
_CANONICAL_ID_PREFIX = "litvar@"

# Upstream returns 400 with body {"detail": "Variant not found: ..."} for an id
# that does not exist. That is a user-recoverable "not found", not an outage.
_NOT_FOUND_STATUS = (400, 404)


def _is_canonical_variant_id(value: str) -> bool:
    """True for an already-canonical LitVar id like ``litvar@rs113993960##``."""
    return value.startswith(_CANONICAL_ID_PREFIX)


def _is_variant_not_found(exc: LitVarAPIError) -> bool:
    """True when an upstream 4xx clearly means 'this variant id does not exist'."""
    return exc.status_code in _NOT_FOUND_STATUS and "not found" in str(exc).lower()
