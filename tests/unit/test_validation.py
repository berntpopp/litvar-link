"""Unit tests for the shared validation module (DRY cluster #1)."""

from __future__ import annotations

import pytest

from litvar_link.exceptions import ValidationError
from litvar_link.validation import (
    normalize_hgvs,
    validate_gene_name,
    validate_limit,
    validate_query,
    validate_rsid,
)


class TestValidateQuery:
    def test_strips_and_returns(self) -> None:
        assert validate_query("  CFH  ") == "CFH"

    @pytest.mark.parametrize("bad", ["", "   ", None])
    def test_empty_rejected(self, bad: str | None) -> None:
        with pytest.raises(ValidationError) as exc:
            validate_query(bad)  # type: ignore[arg-type]
        assert exc.value.field == "query"

    def test_too_long_rejected(self) -> None:
        with pytest.raises(ValidationError) as exc:
            validate_query("x" * 101)
        assert exc.value.field == "query"


class TestValidateLimit:
    @pytest.mark.parametrize("good", [1, 10, 100])
    def test_in_range_ok(self, good: int) -> None:
        assert validate_limit(good) == good

    @pytest.mark.parametrize("bad", [0, -1, 101, 1000])
    def test_out_of_range_rejected(self, bad: int) -> None:
        with pytest.raises(ValidationError) as exc:
            validate_limit(bad)
        assert exc.value.field == "limit"


class TestValidateRsid:
    def test_lowercases_and_returns(self) -> None:
        assert validate_rsid("RS1061170") == "rs1061170"

    @pytest.mark.parametrize("bad", ["", "rs", "rsABC", "1061170", "x1061170"])
    def test_invalid_rejected(self, bad: str) -> None:
        with pytest.raises(ValidationError) as exc:
            validate_rsid(bad)
        assert exc.value.field == "rsid"


class TestValidateGeneName:
    def test_strips_uppercases(self) -> None:
        assert validate_gene_name("  cfh ") == "CFH"

    @pytest.mark.parametrize("bad", ["", "   "])
    def test_empty_rejected(self, bad: str) -> None:
        with pytest.raises(ValidationError) as exc:
            validate_gene_name(bad)
        assert exc.value.field == "gene_name"

    def test_too_long_rejected(self) -> None:
        with pytest.raises(ValidationError) as exc:
            validate_gene_name("G" * 51)
        assert exc.value.field == "gene_name"


class TestNormalizeHgvs:
    def test_strips_refseq_transcript_version(self) -> None:
        assert normalize_hgvs("NM_001458.5:c.6651del") == "NM_001458:c.6651del"

    def test_strips_refseq_genomic_version(self) -> None:
        assert normalize_hgvs("NC_000001.11:g.12345A>G") == "NC_000001:g.12345A>G"

    def test_strips_refseq_protein_version(self) -> None:
        assert normalize_hgvs("NP_001449.1:p.Val600Glu") == "NP_001449:p.Val600Glu"

    def test_strips_ensembl_version(self) -> None:
        assert normalize_hgvs("ENST00000380152.8:c.6651del") == "ENST00000380152:c.6651del"

    def test_strips_bare_refseq_accession_version(self) -> None:
        assert normalize_hgvs("NM_001458.5") == "NM_001458"

    def test_strips_version_in_spaced_query(self) -> None:
        assert normalize_hgvs("NM_001458.5 c.6651del") == "NM_001458 c.6651del"

    def test_leaves_unversioned_hgvs_unchanged(self) -> None:
        assert normalize_hgvs("NM_001458:c.6651del") == "NM_001458:c.6651del"

    def test_leaves_rsid_unchanged(self) -> None:
        assert normalize_hgvs("rs1061170") == "rs1061170"

    def test_validate_query_normalizes_hgvs_version(self) -> None:
        assert validate_query("NM_001458.5:c.6651del") == "NM_001458:c.6651del"
