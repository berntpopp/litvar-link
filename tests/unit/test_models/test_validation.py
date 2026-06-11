"""Comprehensive model validation tests."""

import pytest
from pydantic import ValidationError

from litvar_link.models.endpoint_specific import (
    AutocompleteVariantItem,
    GeneVariantItem,
    PublicationsItem,
    SensorItem,
)
from litvar_link.models.requests import (
    GeneVariantsRequest,
    PublicationRequest,
    SensorRequest,
    VariantSearchRequest,
)
from litvar_link.models.responses import (
    GeneVariantsResponse,
    PublicationResponse,
    SensorResponse,
    VariantSearchResponse,
)


class TestVariantSearchRequest:
    """Test VariantSearchRequest validation."""

    def test_valid_request(self) -> None:
        """Test valid variant search request."""
        request = VariantSearchRequest(query="CFH", limit=10)
        assert request.query == "CFH"
        assert request.limit == 10

    def test_default_limit(self) -> None:
        """Test default limit value."""
        request = VariantSearchRequest(query="CFH")
        assert request.limit == 10

    def test_query_validation_empty(self) -> None:
        """Test empty query validation."""
        with pytest.raises(ValidationError, match="Query cannot be empty"):
            VariantSearchRequest(query="", limit=10)

    def test_query_validation_whitespace(self) -> None:
        """Test whitespace query validation."""
        with pytest.raises(ValidationError, match="Query cannot be empty"):
            VariantSearchRequest(query="   ", limit=10)

    def test_query_validation_too_long(self) -> None:
        """Test query too long validation."""
        with pytest.raises(ValidationError, match="Query too long"):
            VariantSearchRequest(query="x" * 101, limit=10)

    def test_limit_validation_zero(self) -> None:
        """Test zero limit validation."""
        with pytest.raises(ValidationError, match="Limit must be between 1 and 100"):
            VariantSearchRequest(query="CFH", limit=0)

    def test_limit_validation_negative(self) -> None:
        """Test negative limit validation."""
        with pytest.raises(ValidationError, match="Limit must be between 1 and 100"):
            VariantSearchRequest(query="CFH", limit=-1)

    def test_limit_validation_too_large(self) -> None:
        """Test too large limit validation."""
        with pytest.raises(ValidationError, match="Limit must be between 1 and 100"):
            VariantSearchRequest(query="CFH", limit=101)

    def test_special_characters_allowed(self) -> None:
        """Test that special characters are allowed in queries."""
        request = VariantSearchRequest(query="BRCA2 c.317-1G>A", limit=10)
        assert request.query == "BRCA2 c.317-1G>A"

    def test_unicode_characters(self) -> None:
        """Test unicode characters in query."""
        request = VariantSearchRequest(query="β-globin", limit=10)
        assert request.query == "β-globin"


class TestGeneVariantsRequest:
    """Test GeneVariantsRequest validation."""

    def test_valid_request(self) -> None:
        """Test valid gene variants request."""
        request = GeneVariantsRequest(gene_name="CFH")
        assert request.gene_name == "CFH"

    def test_gene_name_validation_empty(self) -> None:
        """Test empty gene name validation."""
        with pytest.raises(ValidationError, match="Gene name cannot be empty"):
            GeneVariantsRequest(gene_name="")

    def test_gene_name_validation_too_long(self) -> None:
        """Test gene name too long validation."""
        with pytest.raises(ValidationError, match="Gene name too long"):
            GeneVariantsRequest(gene_name="x" * 51)

    def test_gene_name_case_preservation(self) -> None:
        """Test that gene name case is preserved."""
        request = GeneVariantsRequest(gene_name="cfh")
        assert request.gene_name == "cfh"


class TestSensorRequest:
    """Test SensorRequest validation."""

    def test_valid_request(self) -> None:
        """Test valid sensor request."""
        request = SensorRequest(rsid="rs1061170")
        assert request.rsid == "rs1061170"

    def test_rsid_validation_invalid_format(self) -> None:
        """Test invalid RSID format validation."""
        with pytest.raises(ValidationError, match="Invalid RSID format"):
            SensorRequest(rsid="invalid_rsid")

    def test_rsid_validation_missing_prefix(self) -> None:
        """Test missing rs prefix validation."""
        with pytest.raises(ValidationError, match="Invalid RSID format"):
            SensorRequest(rsid="1061170")

    def test_rsid_validation_empty(self) -> None:
        """Test empty RSID validation."""
        with pytest.raises(ValidationError, match="Invalid RSID format"):
            SensorRequest(rsid="")

    def test_rsid_validation_only_prefix(self) -> None:
        """Test RSID with only prefix validation."""
        with pytest.raises(ValidationError, match="Invalid RSID format"):
            SensorRequest(rsid="rs")


class TestPublicationRequest:
    """Test PublicationRequest validation."""

    def test_valid_request(self) -> None:
        """Test valid publication request."""
        request = PublicationRequest(variant_id="litvar@rs1061170##")
        assert request.variant_id == "litvar@rs1061170##"

    def test_variant_id_validation_empty(self) -> None:
        """Test empty variant ID validation."""
        with pytest.raises(ValidationError, match="Variant ID cannot be empty"):
            PublicationRequest(variant_id="")


class TestEndpointSpecificModels:
    """Test endpoint-specific models."""

    def test_autocomplete_variant_item_minimal(self) -> None:
        """Test minimal autocomplete variant item."""
        item = AutocompleteVariantItem(
            id="litvar@rs1061170##",
            gene=["CFH"],
            name="p.Y402H",
            pmids_count=834,
        )
        assert item.id == "litvar@rs1061170##"
        assert item.gene == ["CFH"]
        assert item.rsid is None
        assert item.match is None

    def test_autocomplete_variant_item_full(self) -> None:
        """Test full autocomplete variant item."""
        item = AutocompleteVariantItem(
            id="litvar@rs1061170##",
            gene=["CFH"],
            name="p.Y402H",
            pmids_count=834,
            rsid="rs1061170",
            match="CFH <em>p.Y402H</em> (rs1061170)",
        )
        assert item.rsid == "rs1061170"
        assert item.match == "CFH <em>p.Y402H</em> (rs1061170)"

    def test_gene_variant_item_minimal(self) -> None:
        """Test minimal gene variant item."""
        item = GeneVariantItem(id="litvar@rs1061170##", pmids_count=834)
        assert item.id == "litvar@rs1061170##"
        assert item.pmids_count == 834
        assert item.rsid is None
        assert item.clingen_id is None

    def test_gene_variant_item_with_rsid(self) -> None:
        """Test gene variant item with RSID."""
        item = GeneVariantItem(
            id="litvar@rs1061170##",
            pmids_count=834,
            rsid="rs1061170",
        )
        assert item.rsid == "rs1061170"

    def test_sensor_item(self) -> None:
        """Test sensor item."""
        item = SensorItem(
            pmids_count=834,
            rsid="rs1061170",
            link="https://www.ncbi.nlm.nih.gov/research/litvar2/docsum?text=rs1061170",
            logo="https://www.ncbi.nlm.nih.gov/research/litvar2/img/litvar_logo.png",
        )
        assert item.pmids_count == 834
        assert item.rsid == "rs1061170"
        assert item.link == "https://www.ncbi.nlm.nih.gov/research/litvar2/docsum?text=rs1061170"
        assert item.logo == "https://www.ncbi.nlm.nih.gov/research/litvar2/img/litvar_logo.png"

    def test_publications_item(self) -> None:
        """Test publications item."""
        item = PublicationsItem(pmids=[17634449, 18425111])
        assert item.pmids == [17634449, 18425111]


class TestResponseModels:
    """Test response models."""

    def test_variant_search_response(self) -> None:
        """Test variant search response."""
        response = VariantSearchResponse(
            variants=[],
            query="CFH",
            total_count=0,
            limit=10,
            has_more=False,
            search_time_ms=123.45,
            cached=False,
        )
        assert response.variants == []
        assert response.query == "CFH"
        assert response.total_count == 0
        assert response.search_time_ms == 123.45

    def test_gene_variants_response(self) -> None:
        """Test gene variants response."""
        response = GeneVariantsResponse(
            gene="CFH",
            variants=[],
            total_count=0,
            pathogenic_count=0,
            benign_count=0,
            uncertain_count=0,
            total_publications=0,
            cached=False,
            search_time_ms=123.45,
        )
        assert response.gene == "CFH"
        assert response.total_count == 0
        assert response.pathogenic_count == 0

    def test_sensor_response_available(self) -> None:
        """Test sensor response when available."""
        response = SensorResponse(
            rsid="rs1061170",
            available=True,
            pmids_count=834,
            gene=["CFH"],
            variant_name="p.Y402H",
            litvar_url="https://example.com",
            cached=False,
            search_time_ms=123.45,
        )
        assert response.rsid == "rs1061170"
        assert response.available is True
        assert response.pmids_count == 834

    def test_sensor_response_not_available(self) -> None:
        """Test sensor response when not available."""
        response = SensorResponse(
            rsid="rs999999999",
            available=False,
            pmids_count=None,
            gene=None,
            variant_name=None,
            litvar_url=None,
            cached=False,
            search_time_ms=123.45,
        )
        assert response.rsid == "rs999999999"
        assert response.available is False
        assert response.pmids_count is None

    def test_publication_response(self) -> None:
        """Test publication response."""
        from litvar_link.models.variants import Publication

        publications = [
            Publication(pmid="17634449"),
            Publication(pmid="18425111"),
        ]

        response = PublicationResponse(
            variant_id="litvar@rs1061170##",
            publications=publications,
            total_count=2,
            pmid_count=2,
            pmc_count=0,
            format="json",
            cached=False,
        )
        assert response.variant_id == "litvar@rs1061170##"
        assert len(response.publications) == 2
        assert response.total_count == 2
        assert response.pmid_count == 2
        assert len(response.pmids) == 2  # Test the property


class TestModelEdgeCases:
    """Test model edge cases and boundary conditions."""

    def test_negative_counts(self) -> None:
        """Test that negative counts are handled properly."""
        # Test that negative pmids_count is allowed (could indicate error state)
        item = GeneVariantItem(id="test", pmids_count=-1)
        assert item.pmids_count == -1

    def test_large_numbers(self) -> None:
        """Test handling of large numbers."""
        item = GeneVariantItem(id="test", pmids_count=999999)
        assert item.pmids_count == 999999

    def test_empty_lists(self) -> None:
        """Test handling of empty lists."""
        item = AutocompleteVariantItem(
            id="test",
            gene=[],
            name="test",
            pmids_count=0,  # Empty gene list
        )
        assert item.gene == []

    def test_very_long_strings(self) -> None:
        """Test handling of very long strings."""
        long_name = "x" * 1000
        item = AutocompleteVariantItem(
            id="test",
            gene=["TEST"],
            name=long_name,
            pmids_count=0,
        )
        assert item.name == long_name

    def test_special_characters_in_ids(self) -> None:
        """Test special characters in IDs."""
        special_id = "litvar@rs1061170##special!@#$%^&*()"
        item = GeneVariantItem(id=special_id, pmids_count=0)
        assert item.id == special_id

    def test_none_values_where_allowed(self) -> None:
        """Test None values in optional fields."""
        response = SensorResponse(
            rsid="rs123",
            available=False,
            pmids_count=None,
            gene=None,
            variant_name=None,
            litvar_url=None,
            cached=False,
            search_time_ms=0.0,
        )
        assert response.pmids_count is None
        assert response.gene is None
        assert response.variant_name is None
        assert response.litvar_url is None

    def test_zero_search_time(self) -> None:
        """Test zero search time handling."""
        response = VariantSearchResponse(
            variants=[],
            query="test",
            total_count=0,
            limit=10,
            has_more=False,
            search_time_ms=0.0,
            cached=True,  # Could be from cache
        )
        assert response.search_time_ms == 0.0
        assert response.cached is True

    def test_fractional_search_time(self) -> None:
        """Test fractional search time handling."""
        response = VariantSearchResponse(
            variants=[],
            query="test",
            total_count=0,
            limit=10,
            has_more=False,
            search_time_ms=123.456789,
            cached=False,
        )
        assert response.search_time_ms == 123.456789
