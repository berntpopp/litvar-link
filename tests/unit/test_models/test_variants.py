"""Tests for variant models."""

from typing import Any

import pytest
from pydantic import ValidationError

from litvar_link.models.variants import (
    ClinicalSignificance,
    Publication,
    Variant,
    VariantDetails,
)


class TestPublication:
    """Test Publication model."""

    def test_valid_publication(self) -> None:
        """Test creating valid publication."""
        pub = Publication(
            pmid="12345678",
            pmcid="PMC1234567",
            title="Test Publication",
            authors=["Smith J", "Doe A"],
            journal="Nature",
            pub_date="2023-01-15",
            doi="10.1038/test.2023.001",
        )

        assert pub.pmid == "12345678"
        assert pub.pmcid == "PMC1234567"
        assert pub.title == "Test Publication"
        assert len(pub.authors) == 2

    def test_pmid_validation(self) -> None:
        """Test PMID validation."""
        # Valid PMIDs
        pub1 = Publication(pmid="1234567")  # 7 digits
        pub2 = Publication(pmid="12345678")  # 8 digits
        assert pub1.pmid == "1234567"
        assert pub2.pmid == "12345678"

        # Invalid PMIDs
        with pytest.raises(ValidationError):
            Publication(pmid="abc123")  # Contains letters

        with pytest.raises(ValidationError):
            Publication(pmid="123456")  # Too short

        with pytest.raises(ValidationError):
            Publication(pmid="123456789")  # Too long

    def test_pmcid_validation(self) -> None:
        """Test PMCID validation."""
        # Valid PMCIDs
        pub1 = Publication(pmid="12345678", pmcid="PMC1234567")
        pub2 = Publication(pmid="12345678", pmcid=None)
        assert pub1.pmcid == "PMC1234567"
        assert pub2.pmcid is None

        # Invalid PMCIDs
        with pytest.raises(ValidationError):
            Publication(pmid="12345678", pmcid="1234567")  # Missing PMC prefix

        with pytest.raises(ValidationError):
            Publication(pmid="12345678", pmcid="PMCabc123")  # Non-numeric part


class TestVariant:
    """Test Variant model."""

    def test_variant_from_litvar_data(
        self,
        sample_variant_data: dict[str, Any],
    ) -> None:
        """Test creating variant from real LitVar2 data."""
        variant = Variant(**sample_variant_data)

        assert variant.id == "litvar@rs1061170##"
        assert variant.rsid == "rs1061170"
        assert variant.gene == ["CFH"]
        assert variant.name == "p.Y402H"
        assert variant.hgvs == "NP_000177.2:p.Tyr402His"
        assert variant.pmids_count == 834
        assert variant.clinical_significance == ["risk factor", "benign"]
        assert variant.flag_gene_variant is True
        assert variant.flag_rsid_variant is True
        assert variant.match == "CFH <em>p.Y402H</em> (rs1061170)"

    def test_gene_list_normalization(self) -> None:
        """Test gene list normalization."""
        variant = Variant(
            _id="test_variant",
            gene=[
                "cfh",
                "CFH",
                "",
                "brca1",
                "BRCA1",
            ],  # Mixed case with duplicates and empty
        )

        # Should normalize to uppercase and remove duplicates/empty strings
        assert variant.gene == ["CFH", "BRCA1"]

    def test_rsid_validation(self) -> None:
        """Test RSID validation."""
        # Valid RSIDs
        variant1 = Variant(_id="test1", rsid="rs1061170")
        variant2 = Variant(_id="test2", rsid="rs123")
        variant3 = Variant(_id="test3", rsid=None)

        assert variant1.rsid == "rs1061170"
        assert variant2.rsid == "rs123"
        assert variant3.rsid is None

        # Invalid RSIDs
        with pytest.raises(ValidationError):
            Variant(_id="test", rsid="1061170")  # Missing rs prefix

        with pytest.raises(ValidationError):
            Variant(_id="test", rsid="rsabc123")  # Non-numeric part

    def test_pmids_count_validation(self) -> None:
        """Test publication count validation."""
        # Valid counts
        variant1 = Variant(_id="test1", pmids_count=0)
        variant2 = Variant(_id="test2", pmids_count=100)
        variant3 = Variant(_id="test3", pmids_count=None)

        assert variant1.pmids_count == 0
        assert variant2.pmids_count == 100
        assert variant3.pmids_count is None

        # Invalid count
        with pytest.raises(ValidationError):
            Variant(_id="test", pmids_count=-5)

    def test_clinical_significance_validation(self) -> None:
        """Test clinical significance validation."""
        variant = Variant(
            _id="test_variant",
            data_clinical_significance=[
                "PATHOGENIC",
                "Likely Benign",
                "unknown_significance",
            ],
        )

        # Should normalize to lowercase
        assert "pathogenic" in variant.clinical_significance
        assert "likely benign" in variant.clinical_significance
        assert "unknown_significance" in variant.clinical_significance

    def test_display_name_property(self) -> None:
        """Test display name property."""
        # With name
        variant1 = Variant(_id="test1", name="p.Y402H")
        assert variant1.display_name == "p.Y402H"

        # Without name but with RSID
        variant2 = Variant(_id="test2", rsid="rs1061170")
        assert variant2.display_name == "rs1061170"

        # Without name/RSID but with gene
        variant3 = Variant(_id="test3", gene=["CFH"])
        assert variant3.display_name == "CFH variant"

        # Only ID
        variant4 = Variant(_id="test4")
        assert variant4.display_name == "test4"

    def test_pathogenic_property(self) -> None:
        """Test pathogenic property."""
        # Pathogenic variant
        variant1 = Variant(
            _id="test1",
            data_clinical_significance=["pathogenic", "likely pathogenic"],
        )
        assert variant1.is_pathogenic is True

        # Benign variant
        variant2 = Variant(_id="test2", data_clinical_significance=["benign"])
        assert variant2.is_pathogenic is False

        # No significance
        variant3 = Variant(_id="test3")
        assert variant3.is_pathogenic is False

    def test_benign_property(self) -> None:
        """Test benign property."""
        # Benign variant
        variant1 = Variant(
            _id="test1",
            data_clinical_significance=["benign", "likely benign"],
        )
        assert variant1.is_benign is True

        # Pathogenic variant
        variant2 = Variant(_id="test2", data_clinical_significance=["pathogenic"])
        assert variant2.is_benign is False


class TestVariantDetails:
    """Test VariantDetails model."""

    def test_extended_variant_details(self) -> None:
        """Test extended variant with additional details."""
        details = VariantDetails(
            _id="detailed_variant",
            rsid="rs1061170",
            name="p.Y402H",
            chromosome="1",
            position=196690107,
            ref_allele="T",
            alt_allele="C",
            consequence="missense_variant",
            protein_change="p.Tyr402His",
            allele_frequency=0.35,
            minor_allele_frequency=0.35,
        )

        assert details.chromosome == "1"
        assert details.position == 196690107
        assert details.ref_allele == "T"
        assert details.alt_allele == "C"
        assert details.allele_frequency == 0.35

    def test_position_validation(self) -> None:
        """Test genomic position validation."""
        # Valid position
        details1 = VariantDetails(_id="test1", position=100)
        assert details1.position == 100

        # Invalid position
        with pytest.raises(ValidationError):
            VariantDetails(_id="test", position=-1)

        with pytest.raises(ValidationError):
            VariantDetails(_id="test", position=0)

    def test_frequency_validation(self) -> None:
        """Test allele frequency validation."""
        # Valid frequencies
        details1 = VariantDetails(_id="test1", allele_frequency=0.5)
        details2 = VariantDetails(_id="test2", minor_allele_frequency=0.0)
        details3 = VariantDetails(_id="test3", allele_frequency=1.0)

        assert details1.allele_frequency == 0.5
        assert details2.minor_allele_frequency == 0.0
        assert details3.allele_frequency == 1.0

        # Invalid frequencies
        with pytest.raises(ValidationError):
            VariantDetails(_id="test", allele_frequency=-0.1)

        with pytest.raises(ValidationError):
            VariantDetails(_id="test", allele_frequency=1.1)

    def test_chromosome_validation(self) -> None:
        """Test chromosome validation."""
        # Valid chromosomes
        details1 = VariantDetails(_id="test1", chromosome="1")
        details2 = VariantDetails(_id="test2", chromosome="X")
        details3 = VariantDetails(_id="test3", chromosome="MT")
        details4 = VariantDetails(_id="test4", chromosome="chr22")

        assert details1.chromosome == "1"
        assert details2.chromosome == "X"
        assert details3.chromosome == "MT"
        assert details4.chromosome == "22"  # CHR prefix removed

        # Non-standard chromosome (should be preserved)
        details5 = VariantDetails(_id="test5", chromosome="scaffold_123")
        assert details5.chromosome == "SCAFFOLD_123"

    def test_with_publications(self) -> None:
        """Test variant details with publications."""
        publications = [
            Publication(pmid="12345678", title="Test Paper 1"),
            Publication(pmid="87654321", title="Test Paper 2"),
        ]

        details = VariantDetails(_id="test_variant", publications=publications)

        assert len(details.publications) == 2
        assert details.publications[0].pmid == "12345678"
        assert details.publications[1].pmid == "87654321"


class TestClinicalSignificance:
    """Test ClinicalSignificance enum."""

    def test_enum_values(self) -> None:
        """Test clinical significance enum values."""
        assert ClinicalSignificance.PATHOGENIC.value == "pathogenic"
        assert ClinicalSignificance.LIKELY_PATHOGENIC.value == "likely pathogenic"
        assert ClinicalSignificance.BENIGN.value == "benign"
        assert ClinicalSignificance.LIKELY_BENIGN.value == "likely benign"
        assert ClinicalSignificance.UNCERTAIN_SIGNIFICANCE.value == "uncertain significance"
        assert ClinicalSignificance.RISK_FACTOR.value == "risk factor"

    def test_enum_membership(self) -> None:
        """Test checking enum membership."""
        valid_values = {sig.value for sig in ClinicalSignificance}

        assert "pathogenic" in valid_values
        assert "benign" in valid_values
        assert "risk factor" in valid_values
        assert "invalid_significance" not in valid_values
