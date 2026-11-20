"""Unit tests for the shared validation module (DRY cluster #1)."""

from __future__ import annotations

import pytest

from litvar_link.exceptions import ForeignIdentifierError, ValidationError
from litvar_link.validation import (
    genomic_variant_error,
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


class TestForeignIdentifierForms:
    """genefoundry-router #343: a foreign-namespace id is named, never read as "no data"."""

    @pytest.mark.parametrize(
        ("value", "tool", "arguments"),
        [
            ("ENSG00000133703", "hgnc_resolve_symbol", {"query": "ENSG00000133703"}),
            ("ensg00000133703.14", "hgnc_resolve_symbol", {"query": "ENSG00000133703.14"}),
            ("HGNC:6407", "hgnc_resolve_symbol", {"query": "HGNC:6407"}),
            ("NM_004985.5", "hgnc_resolve_symbol", {"query": "NM_004985.5"}),
            ("3845", "hgnc_resolve_gene_by_xref", {"source": "entrez_id", "value": "3845"}),
            (
                "NCBIGene:3845",
                "hgnc_resolve_gene_by_xref",
                {"source": "entrez_id", "value": "3845"},
            ),
        ],
    )
    def test_foreign_gene_id_names_its_converter(
        self, value: str, tool: str, arguments: dict[str, str]
    ) -> None:
        with pytest.raises(ForeignIdentifierError) as exc:
            validate_gene_name(value, field="gene_symbol")
        assert exc.value.field == "gene_symbol"
        assert exc.value.next_commands[0] == {"tool": tool, "arguments": arguments}
        assert value not in str(exc.value)  # fixed message: the input is never echoed

    def test_transcript_id_is_named_without_a_converter(self) -> None:
        with pytest.raises(ForeignIdentifierError) as exc:
            validate_gene_name("ENST00000311936", field="gene_symbol")
        assert "transcript" in exc.value.hint
        assert exc.value.next_commands == []

    @pytest.mark.parametrize("symbol", ["KRAS", "P2RY12", "C4orf3", "H2AX", "NMT1", "ENSA"])
    def test_real_symbols_pass(self, symbol: str) -> None:
        assert validate_gene_name(symbol) == symbol.upper()

    @pytest.mark.parametrize(
        "value",
        ["12-25245350-C-T", "chr12:25245350", "12:25245350:C:T", "chr12:25245350C>T", "X-100-200"],
    )
    def test_coordinate_points_to_the_recoder(self, value: str) -> None:
        error = genomic_variant_error(value, coordinates_only=True)
        assert error is not None
        assert error.next_commands == [
            {"tool": "vep_recode_variant", "arguments": {"variants": [value]}}
        ]

    def test_genomic_hgvs_only_when_asked(self) -> None:
        hgvs = "NC_000012.12:g.25245350C>T"
        assert genomic_variant_error(hgvs, coordinates_only=True) is None
        assert genomic_variant_error(hgvs) is not None

    @pytest.mark.parametrize(
        "value", ["rs1061170", "litvar@rs1061170##", "BRAF V600E", "NM_004333:c.1799T>A", "12"]
    )
    def test_variant_forms_litvar_reads_pass(self, value: str) -> None:
        assert genomic_variant_error(value) is None
