"""Clinical-significance tallying for LitVar2 gene-variant rows.

Extracted from ``variant_service`` because the distinction it encodes -- ABSENT is
not UNCERTAIN -- is the whole of issue #66 D3, and it deserves to be readable on
its own.
"""

from __future__ import annotations

from typing import Any, NamedTuple

_PATHOGENIC = frozenset({"pathogenic", "likely pathogenic"})
_BENIGN = frozenset({"benign", "likely benign"})


class SignificanceCounts(NamedTuple):
    """Clinical-significance tally that keeps ABSENT distinct from UNCERTAIN.

    ``unclassified`` (LitVar2 said nothing) is NOT ``uncertain`` (LitVar2 said
    "uncertain"). Collapsing the two produces a confidently false clinical
    statement -- see ``_count_clinical_significance``.
    """

    pathogenic: int
    benign: int
    uncertain: int
    unclassified: int

    @property
    def classified(self) -> int:
        """Variants for which LitVar2 supplied ANY clinical significance."""
        return self.pathogenic + self.benign + self.uncertain


def _normalize_significance(value: str) -> str:
    """Fold LitVar2's significance tokens to a canonical form.

    Upstream writes ``likely-pathogenic`` / ``risk-factor`` (HYPHENS); the buckets
    were written with spaces (``"likely pathogenic"``), so a genuinely pathogenic
    variant never matched and fell through to "uncertain". A second, quieter
    instance of the same defect as the absent-field recoding below.
    """
    return value.strip().lower().replace("-", " ").replace("_", " ")


def _count_clinical_significance(variants: list[Any]) -> SignificanceCounts:
    """Tally clinical significance, keeping ABSENT strictly apart from UNCERTAIN.

    The old version counted a variant with NO ``data_clinical_significance`` as
    ``uncertain``. LitVar2's gene endpoint never carries that field at all, so
    every variant in every gene was bucketed "uncertain" and then COUNTED,
    yielding the confidently false:

        13,264 BRCA1 variants -- 0 pathogenic, 0 benign, 13,264 uncertain

    BRCA1 has thousands of established pathogenic variants. A curator would have
    believed that. In clinical genetics "uncertain" means VUS -- a positive
    assertion that the evidence was weighed and found inconclusive. It is NOT a
    synonym for "nobody told us". A field that is absent upstream must be
    reported as UNKNOWN, never counted as a negative finding.
    """
    pathogenic = benign = uncertain = unclassified = 0
    for variant in variants:
        sigs = getattr(variant, "data_clinical_significance", None)
        if not sigs:
            unclassified += 1
            continue
        normalized = {_normalize_significance(sig) for sig in sigs}
        if normalized & _PATHOGENIC:
            pathogenic += 1
        elif normalized & _BENIGN:
            benign += 1
        else:
            # Present, but neither a pathogenic nor a benign call (e.g. "risk
            # factor", "association", "uncertain significance").
            uncertain += 1
    return SignificanceCounts(pathogenic, benign, uncertain, unclassified)
