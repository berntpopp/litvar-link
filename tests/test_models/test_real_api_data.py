"""Tests with real LitVar2 API data to validate models."""

import pytest

from litvar_link.models.variants import Variant


class TestRealApiData:
    """Test models with real LitVar2 API responses."""

    def test_cfh_autocomplete_data(self) -> None:
        """Test with real CFH autocomplete response data."""
        # Real data from https://www.ncbi.nlm.nih.gov/research/litvar2-api/variant/autocomplete/?query=CFH
        real_variants = [
            {
                "_id": "litvar@rs1061170##",
                "rsid": "rs1061170",
                "gene": ["CFH"],
                "name": "p.Y402H",
                "hgvs": "NP_000177.2:p.Tyr402His",
                "pmids_count": 834,
                "data_clinical_significance": ["risk factor", "benign"],
                "flag_gene_variant": True,
                "flag_clingen_variant": False,
                "flag_rsid_variant": True,
                "match": "CFH <em>p.Y402H</em> (rs1061170)",
            },
            {
                "_id": "litvar@rs800292##",
                "rsid": "rs800292",
                "gene": ["CFH"],
                "name": "p.I62V",
                "hgvs": "NP_000177.2:p.Ile62Val",
                "pmids_count": 490,
                "data_clinical_significance": ["benign"],
                "flag_gene_variant": True,
                "flag_clingen_variant": False,
                "flag_rsid_variant": True,
                "match": "CFH <em>p.I62V</em> (rs800292)",
            },
            {
                "_id": "litvar@CFH@c.2237-543G>A##",
                "gene": ["CFH"],
                "name": "c.2237-543G>A",
                "pmids_count": 1,
                "flag_gene_variant": True,
                "flag_clingen_variant": False,
                "flag_rsid_variant": False,
                "match": "CFH <em>c.2237-543G>A</em>",
            },
        ]

        # Test each variant can be parsed
        variants = []
        for data in real_variants:
            variant = Variant(**data)
            variants.append(variant)

        # Validate first variant (rs1061170)
        v1 = variants[0]
        assert v1.id == "litvar@rs1061170##"
        assert v1.rsid == "rs1061170"
        assert v1.gene == ["CFH"]
        assert v1.name == "p.Y402H"
        assert v1.pmids_count == 834
        assert v1.clinical_significance == ["risk factor", "benign"]
        assert v1.is_benign is True
        assert v1.is_pathogenic is False
        assert v1.display_name == "p.Y402H"

        # Validate second variant (rs800292)
        v2 = variants[1]
        assert v2.id == "litvar@rs800292##"
        assert v2.rsid == "rs800292"
        assert v2.clinical_significance == ["benign"]
        assert v2.is_benign is True

        # Validate third variant (no RSID)
        v3 = variants[2]
        assert v3.id == "litvar@CFH@c.2237-543G>A##"
        assert v3.rsid is None
        assert v3.name == "c.2237-543G>A"
        assert v3.flag_rsid_variant is False

    def test_gene_variants_data(self) -> None:
        """Test with real gene variants response data."""
        # Real data from https://www.ncbi.nlm.nih.gov/research/litvar2-api/variant/search/gene/CFH
        gene_variants = [
            {
                "_id": "litvar@rs9970784##",
                "rsid": "rs9970784",
                "gene": ["CFH"],
                "name": "p.R661A",
                "pmids_count": 1,
            },
            {
                "_id": "litvar@rs800292##",
                "rsid": "rs800292",
                "gene": ["CFH"],
                "name": "p.I62V",
                "pmids_count": 490,
                "data_clinical_significance": ["benign"],
            },
            {
                "_id": "litvar@CFH@g.3572C>T##",
                "gene": ["CFH"],
                "name": "g.3572C>T",
                "pmids_count": 2,
            },
        ]

        # Parse all variants
        variants = [Variant(**data) for data in gene_variants]

        # Validate parsing worked
        assert len(variants) == 3
        assert all(v.gene == ["CFH"] for v in variants)

        # Check specific variants
        v1 = next(v for v in variants if v.rsid == "rs9970784")
        assert v1.name == "p.R661A"
        assert v1.pmids_count == 1

        v2 = next(v for v in variants if v.name == "g.3572C>T")
        assert v2.rsid is None
        assert v2.pmids_count == 2

    def test_variant_without_optional_fields(self) -> None:
        """Test variant with minimal required fields."""
        minimal_data = {"_id": "litvar@minimal_variant##"}

        variant = Variant(**minimal_data)
        assert variant.id == "litvar@minimal_variant##"
        assert variant.rsid is None
        assert variant.gene is None
        assert variant.name is None
        assert variant.clinical_significance is None
        assert variant.pmids_count is None
        assert variant.display_name == "litvar@minimal_variant##"

    def test_mixed_case_clinical_significance(self) -> None:
        """Test clinical significance normalization with mixed case."""
        data = {
            "_id": "test_variant",
            "data_clinical_significance": [
                "PATHOGENIC",
                "Likely Benign",
                "uncertain Significance",
                "RISK FACTOR",
            ],
        }

        variant = Variant(**data)
        expected = [
            "pathogenic",
            "likely benign",
            "uncertain significance",
            "risk factor",
        ]
        assert variant.clinical_significance == expected
        assert variant.is_pathogenic is True
        assert variant.is_benign is True  # Contains likely benign

    def test_empty_lists_handled_correctly(self) -> None:
        """Test that empty lists are handled properly."""
        data = {"_id": "test_variant", "gene": [], "data_clinical_significance": []}

        variant = Variant(**data)
        assert variant.gene is None
        assert variant.clinical_significance is None
