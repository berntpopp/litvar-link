"""Test request model validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from litvar_link.models.requests import (
    BatchVariantRequest,
    CacheRequest,
    GeneVariantsRequest,
    PublicationRequest,
    SensorRequest,
    VariantDetailsRequest,
    VariantSearchRequest,
)


class TestVariantSearchRequest:
    """Test VariantSearchRequest validation."""

    def test_valid_request(self):
        """Test creating a valid variant search request."""
        request = VariantSearchRequest(query="BRCA1", limit=10)

        assert request.query == "BRCA1"
        assert request.limit == 10

    def test_default_limit(self):
        """Test default limit value."""
        request = VariantSearchRequest(query="CFH")

        assert request.query == "CFH"
        assert request.limit == 10

    def test_query_whitespace_stripping(self):
        """Test that query whitespace is stripped."""
        request = VariantSearchRequest(query="  BRCA1  ")

        assert request.query == "BRCA1"

    def test_query_empty_string(self):
        """Test validation of empty query string."""
        with pytest.raises(ValidationError) as exc_info:
            VariantSearchRequest(query="")

        assert "Query cannot be empty" in str(exc_info.value)

    def test_query_whitespace_only(self):
        """Test validation of whitespace-only query."""
        with pytest.raises(ValidationError) as exc_info:
            VariantSearchRequest(query="   ")

        assert "Query cannot be empty" in str(exc_info.value)

    def test_query_too_long(self):
        """Test validation of overly long query."""
        long_query = "a" * 101

        with pytest.raises(ValidationError) as exc_info:
            VariantSearchRequest(query=long_query)

        assert "Query too long" in str(exc_info.value)

    def test_query_max_length_boundary(self):
        """Test query at maximum length boundary."""
        max_query = "a" * 100
        request = VariantSearchRequest(query=max_query)

        assert request.query == max_query

    @pytest.mark.parametrize("dangerous_char", ["<", "&", '"', ";"])
    def test_query_dangerous_characters(self, dangerous_char):
        """Test validation rejects dangerous characters."""
        query = f"BRCA1{dangerous_char}test"

        with pytest.raises(ValidationError) as exc_info:
            VariantSearchRequest(query=query)

        assert f"Query contains invalid character: {dangerous_char}" in str(
            exc_info.value,
        )

    def test_query_allowed_special_characters(self):
        """Test that allowed special characters pass validation."""
        # The ">" character should be allowed for genetic notation
        request = VariantSearchRequest(query="c.317-1G>A")

        assert request.query == "c.317-1G>A"

    def test_limit_valid_range(self):
        """Test valid limit values."""
        # Test minimum valid limit
        request = VariantSearchRequest(query="test", limit=1)
        assert request.limit == 1

        # Test maximum valid limit
        request = VariantSearchRequest(query="test", limit=100)
        assert request.limit == 100

    def test_limit_too_small(self):
        """Test validation of limit below minimum."""
        with pytest.raises(ValidationError) as exc_info:
            VariantSearchRequest(query="test", limit=0)

        assert "Limit must be between 1 and 100" in str(exc_info.value)

    def test_limit_too_large(self):
        """Test validation of limit above maximum."""
        with pytest.raises(ValidationError) as exc_info:
            VariantSearchRequest(query="test", limit=101)

        assert "Limit must be between 1 and 100" in str(exc_info.value)

    def test_limit_negative(self):
        """Test validation of negative limit."""
        with pytest.raises(ValidationError) as exc_info:
            VariantSearchRequest(query="test", limit=-1)

        assert "Limit must be between 1 and 100" in str(exc_info.value)


class TestVariantDetailsRequest:
    """Test VariantDetailsRequest validation."""

    def test_valid_request(self):
        """Test creating a valid variant details request."""
        request = VariantDetailsRequest(variant_id="rs1061170")

        assert request.variant_id == "rs1061170"

    def test_variant_id_whitespace_stripping(self):
        """Test that variant ID whitespace is stripped."""
        request = VariantDetailsRequest(variant_id="  rs1061170  ")

        assert request.variant_id == "rs1061170"

    def test_variant_id_empty_string(self):
        """Test validation of empty variant ID."""
        with pytest.raises(ValidationError) as exc_info:
            VariantDetailsRequest(variant_id="")

        assert "Variant ID cannot be empty" in str(exc_info.value)

    def test_variant_id_whitespace_only(self):
        """Test validation of whitespace-only variant ID."""
        with pytest.raises(ValidationError) as exc_info:
            VariantDetailsRequest(variant_id="   ")

        assert "Variant ID cannot be empty" in str(exc_info.value)


class TestPublicationRequest:
    """Test PublicationRequest validation."""

    def test_valid_request_defaults(self):
        """Test creating a valid publication request with defaults."""
        request = PublicationRequest(variant_id="rs1061170")

        assert request.variant_id == "rs1061170"
        assert request.format == "json"
        assert request.limit is None

    def test_valid_request_all_fields(self):
        """Test creating a valid publication request with all fields."""
        request = PublicationRequest(
            variant_id="rs1061170",
            format="detailed",
            limit=50,
        )

        assert request.variant_id == "rs1061170"
        assert request.format == "detailed"
        assert request.limit == 50

    def test_variant_id_validation(self):
        """Test variant ID validation."""
        with pytest.raises(ValidationError) as exc_info:
            PublicationRequest(variant_id="")

        assert "Variant ID cannot be empty" in str(exc_info.value)

    def test_format_validation(self):
        """Test format field validation."""
        # Valid formats
        for fmt in ["json", "pmid_list", "detailed"]:
            request = PublicationRequest(variant_id="test", format=fmt)
            assert request.format == fmt

    def test_format_invalid(self):
        """Test invalid format value."""
        with pytest.raises(ValidationError):
            PublicationRequest(variant_id="test", format="invalid_format")

    def test_limit_boundaries(self):
        """Test limit field boundaries."""
        # Valid limits
        request = PublicationRequest(variant_id="test", limit=1)
        assert request.limit == 1

        request = PublicationRequest(variant_id="test", limit=1000)
        assert request.limit == 1000

    def test_limit_invalid_range(self):
        """Test invalid limit values."""
        # Below minimum
        with pytest.raises(ValidationError):
            PublicationRequest(variant_id="test", limit=0)

        # Above maximum
        with pytest.raises(ValidationError):
            PublicationRequest(variant_id="test", limit=1001)


class TestSensorRequest:
    """Test SensorRequest validation."""

    def test_valid_rsid(self):
        """Test valid RSID formats."""
        valid_rsids = ["rs1", "rs123", "rs1061170", "rs123456789012345"]

        for rsid in valid_rsids:
            request = SensorRequest(rsid=rsid)
            assert request.rsid == rsid

    def test_rsid_whitespace_stripping(self):
        """Test that RSID whitespace is stripped."""
        request = SensorRequest(rsid="  rs1061170  ")

        assert request.rsid == "rs1061170"

    def test_rsid_empty_string(self):
        """Test validation of empty RSID."""
        with pytest.raises(ValidationError) as exc_info:
            SensorRequest(rsid="")

        assert "Invalid RSID format" in str(exc_info.value)

    def test_rsid_whitespace_only(self):
        """Test validation of whitespace-only RSID."""
        with pytest.raises(ValidationError) as exc_info:
            SensorRequest(rsid="   ")

        assert "Invalid RSID format" in str(exc_info.value)

    def test_rsid_missing_prefix(self):
        """Test validation of RSID without 'rs' prefix."""
        with pytest.raises(ValidationError) as exc_info:
            SensorRequest(rsid="1061170")

        assert "Invalid RSID format" in str(exc_info.value)

    def test_rsid_wrong_prefix(self):
        """Test validation of RSID with wrong prefix."""
        with pytest.raises(ValidationError) as exc_info:
            SensorRequest(rsid="cs1061170")

        assert "Invalid RSID format" in str(exc_info.value)

    def test_rsid_no_numeric_part(self):
        """Test validation of RSID with no numeric part."""
        with pytest.raises(ValidationError) as exc_info:
            SensorRequest(rsid="rs")

        assert "Invalid RSID format" in str(exc_info.value)

    def test_rsid_non_numeric_part(self):
        """Test validation of RSID with non-numeric part."""
        with pytest.raises(ValidationError) as exc_info:
            SensorRequest(rsid="rsabc123")

        assert "Invalid RSID format" in str(exc_info.value)

    def test_rsid_numeric_part_too_long(self):
        """Test validation of RSID with overly long numeric part."""
        long_rsid = "rs" + "1" * 16  # 16 digits is too long

        with pytest.raises(ValidationError) as exc_info:
            SensorRequest(rsid=long_rsid)

        assert "Invalid RSID format" in str(exc_info.value)

    def test_rsid_numeric_part_max_length(self):
        """Test RSID with maximum valid numeric length."""
        max_rsid = "rs" + "1" * 15  # 15 digits should be valid
        request = SensorRequest(rsid=max_rsid)

        assert request.rsid == max_rsid


class TestGeneVariantsRequest:
    """Test GeneVariantsRequest validation."""

    def test_valid_request_defaults(self):
        """Test creating a valid gene variants request with defaults."""
        request = GeneVariantsRequest(gene_name="CFH")

        assert request.gene_name == "CFH"
        assert request.limit is None
        assert request.sort_by == "pmids_count"
        assert request.sort_order == "desc"

    def test_valid_request_all_fields(self):
        """Test creating a valid gene variants request with all fields."""
        request = GeneVariantsRequest(
            gene_name="BRCA1",
            limit=50,
            sort_by="name",
            sort_order="asc",
        )

        assert request.gene_name == "BRCA1"
        assert request.limit == 50
        assert request.sort_by == "name"
        assert request.sort_order == "asc"

    def test_gene_name_whitespace_stripping(self):
        """Test that gene name whitespace is stripped."""
        request = GeneVariantsRequest(gene_name="  CFH  ")

        assert request.gene_name == "CFH"

    def test_gene_name_empty_string(self):
        """Test validation of empty gene name."""
        with pytest.raises(ValidationError) as exc_info:
            GeneVariantsRequest(gene_name="")

        assert "Gene name cannot be empty" in str(exc_info.value)

    def test_gene_name_whitespace_only(self):
        """Test validation of whitespace-only gene name."""
        with pytest.raises(ValidationError) as exc_info:
            GeneVariantsRequest(gene_name="   ")

        assert "Gene name cannot be empty" in str(exc_info.value)

    def test_gene_name_valid_characters(self):
        """Test valid gene name characters."""
        valid_names = ["CFH", "BRCA1", "NAA10", "HLA-A", "C1_orf123", "ABC-DEF"]

        for name in valid_names:
            request = GeneVariantsRequest(gene_name=name)
            assert request.gene_name == name

    def test_gene_name_invalid_characters(self):
        """Test invalid gene name characters."""
        with pytest.raises(ValidationError) as exc_info:
            GeneVariantsRequest(gene_name="CFH@test")

        assert "Gene name contains invalid characters" in str(exc_info.value)

    def test_gene_name_too_long(self):
        """Test validation of overly long gene name."""
        long_name = "a" * 51

        with pytest.raises(ValidationError) as exc_info:
            GeneVariantsRequest(gene_name=long_name)

        assert "Gene name too long" in str(exc_info.value)

    def test_gene_name_max_length_boundary(self):
        """Test gene name at maximum length boundary."""
        max_name = "a" * 50
        request = GeneVariantsRequest(gene_name=max_name)

        assert request.gene_name == max_name

    def test_limit_boundaries(self):
        """Test limit field boundaries."""
        # Valid limits
        request = GeneVariantsRequest(gene_name="CFH", limit=1)
        assert request.limit == 1

        request = GeneVariantsRequest(gene_name="CFH", limit=1000)
        assert request.limit == 1000

    def test_limit_invalid_range(self):
        """Test invalid limit values."""
        # Below minimum
        with pytest.raises(ValidationError):
            GeneVariantsRequest(gene_name="CFH", limit=0)

        # Above maximum
        with pytest.raises(ValidationError):
            GeneVariantsRequest(gene_name="CFH", limit=1001)

    def test_sort_by_validation(self):
        """Test sort_by field validation."""
        valid_sort_fields = ["pmids_count", "name", "rsid"]

        for sort_by in valid_sort_fields:
            request = GeneVariantsRequest(gene_name="CFH", sort_by=sort_by)
            assert request.sort_by == sort_by

    def test_sort_by_invalid(self):
        """Test invalid sort_by value."""
        with pytest.raises(ValidationError):
            GeneVariantsRequest(gene_name="CFH", sort_by="invalid_field")

    def test_sort_order_validation(self):
        """Test sort_order field validation."""
        for order in ["asc", "desc"]:
            request = GeneVariantsRequest(gene_name="CFH", sort_order=order)
            assert request.sort_order == order

    def test_sort_order_invalid(self):
        """Test invalid sort_order value."""
        with pytest.raises(ValidationError):
            GeneVariantsRequest(gene_name="CFH", sort_order="invalid_order")


class TestBatchVariantRequest:
    """Test BatchVariantRequest validation."""

    def test_valid_request_defaults(self):
        """Test creating a valid batch request with defaults."""
        request = BatchVariantRequest(variant_ids=["rs1", "rs2"])

        assert request.variant_ids == ["rs1", "rs2"]
        assert request.include_publications is False
        assert request.format == "json"

    def test_valid_request_all_fields(self):
        """Test creating a valid batch request with all fields."""
        request = BatchVariantRequest(
            variant_ids=["rs1", "rs2"],
            include_publications=True,
            format="csv",
        )

        assert request.variant_ids == ["rs1", "rs2"]
        assert request.include_publications is True
        assert request.format == "csv"

    def test_variant_ids_empty_list(self):
        """Test validation of empty variant IDs list."""
        with pytest.raises(ValidationError) as exc_info:
            BatchVariantRequest(variant_ids=[])

        # Check for either custom message or Pydantic's built-in message
        error_message = str(exc_info.value)
        assert (
            "At least one variant ID is required" in error_message
            or "at least 1 item" in error_message
            or "too_short" in error_message
        )

    def test_variant_ids_all_empty_strings(self):
        """Test validation when all variant IDs are empty."""
        with pytest.raises(ValidationError) as exc_info:
            BatchVariantRequest(variant_ids=["", "  ", "\t"])

        assert "No valid variant IDs provided" in str(exc_info.value)

    def test_variant_ids_duplicate_removal(self):
        """Test that duplicate variant IDs are removed."""
        request = BatchVariantRequest(variant_ids=["rs1", "rs2", "rs1", "rs3"])

        assert request.variant_ids == ["rs1", "rs2", "rs3"]

    def test_variant_ids_whitespace_handling(self):
        """Test that whitespace is handled correctly."""
        request = BatchVariantRequest(variant_ids=["  rs1  ", "rs2", "", "  rs3  "])

        assert request.variant_ids == ["rs1", "rs2", "rs3"]

    def test_variant_ids_max_count(self):
        """Test maximum variant IDs limit."""
        # Should work with exactly 100 IDs
        ids_100 = [f"rs{i}" for i in range(100)]
        request = BatchVariantRequest(variant_ids=ids_100)
        assert len(request.variant_ids) == 100

        # Should fail with 101 IDs
        ids_101 = [f"rs{i}" for i in range(101)]
        with pytest.raises(ValidationError) as exc_info:
            BatchVariantRequest(variant_ids=ids_101)

        # Check for either custom message or Pydantic's built-in message
        error_message = str(exc_info.value)
        assert (
            "Maximum 100 variant IDs allowed per request" in error_message
            or "at most 100 items" in error_message
            or "too_long" in error_message
        )

    def test_format_validation(self):
        """Test format field validation."""
        valid_formats = ["json", "csv", "tsv"]

        for fmt in valid_formats:
            request = BatchVariantRequest(variant_ids=["rs1"], format=fmt)
            assert request.format == fmt

    def test_format_invalid(self):
        """Test invalid format value."""
        with pytest.raises(ValidationError):
            BatchVariantRequest(variant_ids=["rs1"], format="invalid_format")


class TestCacheRequest:
    """Test CacheRequest validation."""

    def test_valid_request_no_keys(self):
        """Test creating a valid cache request without keys."""
        request = CacheRequest(operation="clear")

        assert request.operation == "clear"
        assert request.keys is None

    def test_valid_request_with_keys(self):
        """Test creating a valid cache request with keys."""
        request = CacheRequest(operation="clear", keys=["key1", "key2"])

        assert request.operation == "clear"
        assert request.keys == ["key1", "key2"]

    def test_operation_validation(self):
        """Test operation field validation."""
        valid_operations = ["clear", "stats", "warm"]

        for operation in valid_operations:
            request = CacheRequest(operation=operation)
            assert request.operation == operation

    def test_operation_invalid(self):
        """Test invalid operation value."""
        with pytest.raises(ValidationError):
            CacheRequest(operation="invalid_operation")

    def test_keys_whitespace_handling(self):
        """Test that keys whitespace is handled correctly."""
        request = CacheRequest(
            operation="clear",
            keys=["  key1  ", "key2", "", "  key3  ", "   "],
        )

        assert request.keys == ["key1", "key2", "key3"]

    def test_keys_all_empty(self):
        """Test when all keys are empty after processing."""
        request = CacheRequest(operation="clear", keys=["", "  ", "\t"])

        assert request.keys is None

    def test_keys_none_value(self):
        """Test explicitly setting keys to None."""
        request = CacheRequest(operation="stats", keys=None)

        assert request.keys is None
