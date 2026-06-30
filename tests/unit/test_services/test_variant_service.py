"""Comprehensive tests for VariantService."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from litvar_link.config import CacheConfig
from litvar_link.exceptions import LitVarAPIError, ValidationError
from litvar_link.models import (
    GeneVariantsResponse,
    PublicationResponse,
    SensorResponse,
    VariantSearchResponse,
)
from litvar_link.services.variant_service import VariantService


class TestVariantService:
    """Test VariantService with mocked dependencies."""

    @pytest.fixture
    def cache_config(self) -> CacheConfig:
        """Create test cache config."""
        return CacheConfig(
            size=100,
            ttl=300,  # 5 minutes
            stats_enabled=True,
            cleanup_interval=60,
        )

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        """Create mock LitVar2 client."""
        client = AsyncMock()
        client.search_variants = AsyncMock()
        client.get_variant_details = AsyncMock()
        client.get_variant_publications = AsyncMock()
        client.sensor_lookup = AsyncMock()
        client.get_variants_by_gene = AsyncMock()
        return client

    @pytest.fixture
    def mock_logger(self) -> MagicMock:
        """Create mock logger."""
        return MagicMock()

    @pytest.fixture
    def service(
        self,
        mock_client: AsyncMock,
        cache_config: CacheConfig,
        mock_logger: MagicMock,
    ) -> VariantService:
        """Create VariantService instance."""
        return VariantService(
            client=mock_client,
            cache_config=cache_config,
            logger=mock_logger,
        )

    @pytest.mark.asyncio
    async def test_search_variants_success(
        self,
        service: VariantService,
        mock_client: AsyncMock,
        sample_variant_data: dict,
    ) -> None:
        """Test successful variant search."""
        # Mock client response
        mock_client.search_variants.return_value = [sample_variant_data]

        # Call service method
        result = await service.search_variants(query="CFH", limit=10)

        # Verify response structure
        assert isinstance(result, VariantSearchResponse)
        assert len(result.variants) == 1
        assert result.variants[0].id == "litvar@rs1061170##"
        assert result.variants[0].rsid == "rs1061170"
        assert result.query == "CFH"
        assert result.total_count == 1
        assert result.limit == 10
        assert not result.cached  # First call should not be cached
        assert result.search_time_ms > 0

        # Verify client was called correctly
        mock_client.search_variants.assert_called_once_with("CFH", limit=10)

    @pytest.mark.asyncio
    async def test_search_variants_caching(
        self,
        service: VariantService,
        mock_client: AsyncMock,
        sample_variant_data: dict,
    ) -> None:
        """Test that search results are cached correctly."""
        # Mock client response
        mock_client.search_variants.return_value = [sample_variant_data]

        # First call
        result1 = await service.search_variants(query="CFH", limit=10)
        assert not result1.cached

        # Second call with same parameters should be cached
        result2 = await service.search_variants(query="CFH", limit=10)
        assert result2.cached
        assert result2.variants[0].id == result1.variants[0].id

        # Verify client was only called once
        mock_client.search_variants.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_variants_different_params_not_cached(
        self,
        service: VariantService,
        mock_client: AsyncMock,
        sample_variant_data: dict,
    ) -> None:
        """Test that different parameters don't use cache."""
        # Mock client response
        mock_client.search_variants.return_value = [sample_variant_data]

        # Call with different parameters
        await service.search_variants(query="CFH", limit=10)
        await service.search_variants(query="CFH", limit=5)  # Different limit
        await service.search_variants(query="BRCA1", limit=10)  # Different query

        # Should have made 3 separate client calls
        assert mock_client.search_variants.call_count == 3

    @pytest.mark.asyncio
    async def test_search_variants_validation_error(
        self,
        service: VariantService,
        mock_client: AsyncMock,
    ) -> None:
        """Test validation error handling in search."""
        with pytest.raises(ValidationError, match="Query cannot be empty"):
            await service.search_variants(query="", limit=10)

        with pytest.raises(ValidationError, match="Query too long"):
            await service.search_variants(query="x" * 101, limit=10)

        with pytest.raises(ValidationError, match="Limit must be between"):
            await service.search_variants(query="CFH", limit=0)

    @pytest.mark.asyncio
    async def test_search_variants_api_error_propagation(
        self,
        service: VariantService,
        mock_client: AsyncMock,
    ) -> None:
        """Test that API errors are properly propagated."""
        # Mock client to raise API error
        mock_client.search_variants.side_effect = LitVarAPIError("API Error")

        with pytest.raises(LitVarAPIError, match="API Error"):
            await service.search_variants(query="CFH", limit=10)

    @pytest.mark.asyncio
    async def test_lookup_rsid_success(
        self,
        service: VariantService,
        mock_client: AsyncMock,
        sample_sensor_data: dict,
    ) -> None:
        """Test successful RSID lookup."""
        # Mock client response
        mock_client.sensor_lookup.return_value = sample_sensor_data

        # Call service method
        result = await service.lookup_rsid("rs1061170")

        # Verify response structure
        assert isinstance(result, SensorResponse)
        assert result.available is True
        assert result.rsid == "rs1061170"
        assert result.pmids_count == 834
        assert result.litvar_url is not None
        assert not result.cached

        # Verify client was called correctly
        mock_client.sensor_lookup.assert_called_once_with("rs1061170")

    @pytest.mark.asyncio
    async def test_lookup_rsid_not_found(
        self,
        service: VariantService,
        mock_client: AsyncMock,
    ) -> None:
        """Test RSID lookup when variant not found."""
        # Mock client to return None (not found)
        mock_client.sensor_lookup.return_value = None

        # Call service method
        result = await service.lookup_rsid("rs999999999")

        # Verify response structure
        assert isinstance(result, SensorResponse)
        assert result.available is False
        assert result.rsid == "rs999999999"
        assert result.pmids_count is None
        assert result.litvar_url is None

    @pytest.mark.asyncio
    async def test_lookup_rsid_validation(
        self,
        service: VariantService,
        mock_client: AsyncMock,
    ) -> None:
        """Test RSID validation in lookup."""
        with pytest.raises(ValidationError, match="Invalid RSID format"):
            await service.lookup_rsid("invalid_rsid")

        with pytest.raises(ValidationError, match="Invalid RSID format"):
            await service.lookup_rsid("1061170")  # Missing rs prefix

    @pytest.mark.asyncio
    async def test_lookup_rsid_populates_canonical_fields_from_autocomplete(
        self,
        service: VariantService,
        mock_client: AsyncMock,
    ) -> None:
        """resolve_rsid must return populated variant_id/gene/variant_name so the
        result chains downstream. The sensor payload carries only pmids_count +
        link, so the three fields are enriched from autocomplete (issue #20).
        """
        mock_client.sensor_lookup.return_value = {
            "pmids_count": 884,
            "rsid": "rs1061170",
            "link": (
                "https://www.ncbi.nlm.nih.gov/research/litvar2/docsum"
                "?variant=litvar%40rs1061170%23%23&query=rs1061170"
            ),
            "logo": "https://www.ncbi.nlm.nih.gov/research/litvar2/assets/litvar-logo-small.png",
        }
        mock_client.search_variants.return_value = [
            {
                "_id": "litvar@rs1061170##",
                "rsid": "rs1061170",
                "gene": ["CFH"],
                "name": "p.Y402H",
                "hgvs": "p.Y402H",
                "pmids_count": 884,
            },
        ]
        result = await service.lookup_rsid("rs1061170")
        assert result.available is True
        assert result.variant_id == "litvar@rs1061170##"
        assert result.gene == ["CFH"]
        assert result.variant_name == "p.Y402H"
        assert result.litvar_url is not None
        assert result.pmids_count == 884

    @pytest.mark.asyncio
    async def test_lookup_rsid_upstream_not_found_is_unavailable(
        self,
        service: VariantService,
        mock_client: AsyncMock,
    ) -> None:
        """The live sensor endpoint 400s with 'Variant not found' for an unknown
        rsID; resolve_rsid maps that to available=False (recoverable), not an
        internal error, and never calls autocomplete.
        """
        mock_client.sensor_lookup.side_effect = LitVarAPIError(
            'HTTP 400: {"detail":"Variant not found: litvar@rs999999999##"}',
            status_code=400,
        )
        result = await service.lookup_rsid("rs999999999")
        assert result.available is False
        assert result.variant_id is None
        mock_client.search_variants.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_search_gene_variants_success(
        self,
        service: VariantService,
        mock_client: AsyncMock,
        sample_gene_variants_data: list,
    ) -> None:
        """Test successful gene variants search."""
        # Mock client response
        mock_client.get_variants_by_gene.return_value = sample_gene_variants_data

        # Call service method
        result = await service.search_gene_variants("CFH")

        # Verify response structure
        assert isinstance(result, GeneVariantsResponse)
        assert result.gene == "CFH"
        assert len(result.variants) == 3
        assert result.total_count == 3
        assert not result.cached

        # Verify variants have proper data
        variant_with_rsid = next(v for v in result.variants if v.rsid == "rs9970784")
        assert variant_with_rsid.pmids_count == 1

        # Verify statistics calculation
        total_pmids = sum(v.pmids_count for v in result.variants if v.pmids_count)
        assert result.total_publications == total_pmids

    @pytest.mark.asyncio
    async def test_search_gene_variants_statistics(
        self,
        service: VariantService,
        mock_client: AsyncMock,
    ) -> None:
        """Test gene variants statistics calculation."""
        # Mock response with variants having clinical significance
        mock_data = [
            {
                "_id": "var1",
                "rsid": "rs1",
                "pmids_count": 10,
                "data_clinical_significance": ["pathogenic"],
            },
            {
                "_id": "var2",
                "rsid": "rs2",
                "pmids_count": 5,
                "data_clinical_significance": ["benign"],
            },
            {
                "_id": "var3",
                "rsid": "rs3",
                "pmids_count": 3,
                "data_clinical_significance": ["uncertain significance"],
            },
            {
                "_id": "var4",
                "rsid": "rs4",
                "pmids_count": 1,
                # No clinical significance
            },
        ]

        mock_client.get_variants_by_gene.return_value = mock_data

        result = await service.search_gene_variants("TEST")

        # Verify statistics
        assert result.pathogenic_count == 1
        assert result.benign_count == 1
        assert result.uncertain_count == 2  # var3 + var4 (no clinical significance)
        assert result.total_publications == 19  # 10 + 5 + 3 + 1

    @pytest.mark.asyncio
    async def test_search_gene_variants_validation(
        self,
        service: VariantService,
        mock_client: AsyncMock,
    ) -> None:
        """Test gene name validation."""
        with pytest.raises(ValidationError, match="Gene name cannot be empty"):
            await service.search_gene_variants("")

        with pytest.raises(ValidationError, match="Gene name too long"):
            await service.search_gene_variants("x" * 51)

    @pytest.mark.asyncio
    async def test_get_variant_literature_success(
        self,
        service: VariantService,
        mock_client: AsyncMock,
        sample_publication_data: list,
    ) -> None:
        """Test successful variant literature retrieval."""
        # Mock client response
        mock_client.get_variant_publications.return_value = sample_publication_data

        # Call service method
        result = await service.get_variant_literature("litvar@rs1061170##")

        # Verify response structure
        assert isinstance(result, PublicationResponse)
        assert result.variant_id == "litvar@rs1061170##"
        assert len(result.pmids) == 5
        assert result.total_count == 5
        assert not result.cached

        # Verify PMIDs are preserved
        assert "17634449" in result.pmids
        assert "21602305" in result.pmids

    @pytest.mark.asyncio
    async def test_get_variant_literature_validation(
        self,
        service: VariantService,
        mock_client: AsyncMock,
    ) -> None:
        """Test variant ID validation in literature retrieval."""
        with pytest.raises(ValidationError, match="Variant ID cannot be empty"):
            await service.get_variant_literature("")

    @pytest.mark.asyncio
    async def test_get_variant_literature_resolves_rsid_to_canonical_id(
        self,
        service: VariantService,
        mock_client: AsyncMock,
    ) -> None:
        """An rsID is resolved to the canonical litvar id via autocomplete before
        the publications call -- the publications endpoint only accepts
        litvar@...##, so forwarding a raw rsID produces a 400.
        """
        mock_client.search_variants.return_value = [
            {
                "_id": "litvar@rs113993960##",
                "rsid": "rs113993960",
                "gene": ["CFTR"],
                "name": "p.F508del",
                "pmids_count": 2,
            },
        ]
        mock_client.get_variant_publications.return_value = ["37388288", "18022401"]

        result = await service.get_variant_literature("rs113993960")

        mock_client.search_variants.assert_awaited_once()
        mock_client.get_variant_publications.assert_awaited_once_with(
            "litvar@rs113993960##",
        )
        assert result.variant_id == "litvar@rs113993960##"
        assert result.total_count == 2

    @pytest.mark.asyncio
    async def test_get_variant_literature_canonical_id_skips_resolution(
        self,
        service: VariantService,
        mock_client: AsyncMock,
    ) -> None:
        """An already-canonical litvar id is used directly: no autocomplete call."""
        mock_client.get_variant_publications.return_value = ["37388288"]

        result = await service.get_variant_literature("litvar@rs1061170##")

        mock_client.search_variants.assert_not_awaited()
        mock_client.get_variant_publications.assert_awaited_once_with(
            "litvar@rs1061170##",
        )
        assert result.variant_id == "litvar@rs1061170##"

    @pytest.mark.asyncio
    async def test_get_variant_literature_unresolvable_raises_validation(
        self,
        service: VariantService,
        mock_client: AsyncMock,
    ) -> None:
        """When autocomplete finds nothing the entry point fails RECOVERABLY
        (ValidationError -> visible ToolValidationError), never a masked
        'retry later' internal error, and never touches publications.
        """
        mock_client.search_variants.return_value = []

        with pytest.raises(ValidationError, match="No LitVar2 variant found"):
            await service.get_variant_literature("rs000000000")

        mock_client.get_variant_publications.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_get_variant_literature_upstream_not_found_is_recoverable(
        self,
        service: VariantService,
        mock_client: AsyncMock,
    ) -> None:
        """An upstream 'variant not found' 4xx surfaces as a recoverable
        ValidationError, NOT the masked 'retry later' internal error.
        """
        mock_client.get_variant_publications.side_effect = LitVarAPIError(
            'HTTP 400: {"detail":"Variant not found: litvar@rs0##"}',
            status_code=400,
        )

        with pytest.raises(ValidationError, match="variant not found"):
            await service.get_variant_literature("litvar@rs0##")

    @pytest.mark.asyncio
    async def test_get_variant_literature_outage_stays_transient(
        self,
        service: VariantService,
        mock_client: AsyncMock,
    ) -> None:
        """A genuine upstream outage (5xx) is NOT rewritten to not-found: it stays
        a ServiceUnavailableError so the agent's retry-later guidance is correct.
        """
        from litvar_link.exceptions import ServiceUnavailableError

        mock_client.get_variant_publications.side_effect = ServiceUnavailableError(
            "LitVar2 service error: HTTP 503",
        )

        with pytest.raises(ServiceUnavailableError):
            await service.get_variant_literature("litvar@rs0##")

    @pytest.mark.asyncio
    async def test_cache_statistics(
        self,
        service: VariantService,
        mock_client: AsyncMock,
        sample_variant_data: dict,
    ) -> None:
        """Test cache statistics tracking."""
        # Mock client response
        mock_client.search_variants.return_value = [sample_variant_data]

        # Initial cache stats
        initial_stats = service.cache_stats
        assert initial_stats["hits"] == 0
        assert initial_stats["misses"] == 0
        assert initial_stats["hit_rate"] == 0.0

        # Make a call (cache miss)
        await service.search_variants("CFH", limit=10)

        # Make same call again (cache hit)
        await service.search_variants("CFH", limit=10)

        # Check updated stats
        stats = service.cache_stats
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 50.0
        assert stats["total_requests"] == 2

    @pytest.mark.asyncio
    async def test_concurrent_cache_access(
        self,
        service: VariantService,
        mock_client: AsyncMock,
        sample_variant_data: dict,
    ) -> None:
        """Test concurrent access to cached data."""

        # Mock client response with delay to test concurrency
        async def delayed_response(*_args, **_kwargs):
            await asyncio.sleep(0.1)
            return [sample_variant_data]

        mock_client.search_variants.side_effect = delayed_response

        # Make concurrent calls with same parameters
        tasks = [
            service.search_variants("CFH", limit=10),
            service.search_variants("CFH", limit=10),
            service.search_variants("CFH", limit=10),
        ]

        results = await asyncio.gather(*tasks)

        # All should return same data
        assert all(len(r.variants) == 1 for r in results)
        assert all(r.variants[0].id == "litvar@rs1061170##" for r in results)

    @pytest.mark.asyncio
    async def test_search_variants_malformed_data_handling(
        self,
        service: VariantService,
        mock_client: AsyncMock,
        mock_logger: MagicMock,
        sample_variant_data: dict,
    ) -> None:
        """Test handling of malformed variant data during parsing."""
        # Mock client to return mix of valid and invalid data
        invalid_data = {"invalid": "data"}  # Missing required fields
        mock_client.search_variants.return_value = [
            sample_variant_data,  # Valid data
            invalid_data,  # Invalid data that will cause parsing error
            sample_variant_data,  # Another valid data
        ]

        result = await service.search_variants("CFH", limit=10)

        # Should only return valid variants (2 out of 3)
        assert len(result.variants) == 2
        assert result.total_count == 2

        # Should log error for invalid data
        mock_logger.error.assert_called()

    @pytest.mark.asyncio
    async def test_search_gene_variants_exception_handling(
        self,
        service: VariantService,
        mock_client: AsyncMock,
        mock_logger: MagicMock,
    ) -> None:
        """Test exception handling in search_gene_variants."""
        # Mock client to raise exception
        mock_client.get_variants_by_gene.side_effect = Exception("API connection error")

        with pytest.raises(Exception, match="API connection error"):
            await service.search_gene_variants("CFH")

    @pytest.mark.asyncio
    async def test_search_gene_variants_malformed_data(
        self,
        service: VariantService,
        mock_client: AsyncMock,
        mock_logger: MagicMock,
    ) -> None:
        """Test handling of malformed gene variant data."""
        # Mock client to return mix of valid and invalid data
        valid_data = {
            "_id": "valid_variant",
            "rsid": "rs123",
            "pmids_count": 5,
            "data_clinical_significance": ["pathogenic"],
        }
        invalid_data = {"invalid": "structure"}

        mock_client.get_variants_by_gene.return_value = [
            valid_data,
            invalid_data,  # This will cause parsing error
            valid_data,
        ]

        result = await service.search_gene_variants("CFH")

        # Should only include valid variants
        assert len(result.variants) == 2
        assert result.total_count == 2

        # Should log error for invalid data
        mock_logger.error.assert_called()

    @pytest.mark.asyncio
    async def test_lookup_rsid_exception_handling(
        self,
        service: VariantService,
        mock_client: AsyncMock,
        mock_logger: MagicMock,
    ) -> None:
        """Test exception handling in lookup_rsid."""
        # Mock client to raise exception
        mock_client.sensor_lookup.side_effect = Exception("Sensor API error")

        with pytest.raises(Exception, match="Sensor API error"):
            await service.lookup_rsid("rs1061170")

    @pytest.mark.asyncio
    async def test_get_variant_literature_exception_handling(
        self,
        service: VariantService,
        mock_client: AsyncMock,
        mock_logger: MagicMock,
    ) -> None:
        """Test exception handling in get_variant_literature."""
        # Mock client to raise exception
        mock_client.get_variant_publications.side_effect = Exception(
            "Publications API error",
        )

        # Use a canonical id so resolution is skipped and the publications call
        # (the path under test) is reached.
        with pytest.raises(Exception, match="Publications API error"):
            await service.get_variant_literature("litvar@rs1061170##")

    @pytest.mark.asyncio
    async def test_get_variant_summary_exception_handling(
        self,
        service: VariantService,
        mock_client: AsyncMock,
        mock_logger: MagicMock,
    ) -> None:
        """Test exception handling in get_variant_summary."""
        # Mock client to raise exception
        mock_client.get_variant_details.side_effect = Exception("Details API error")

        with pytest.raises(Exception, match="Details API error"):
            await service.get_variant_summary("test_variant_id")

    @pytest.mark.asyncio
    async def test_batch_variant_lookup_exception_handling(
        self,
        service: VariantService,
        mock_client: AsyncMock,
        mock_logger: MagicMock,
    ) -> None:
        """Test exception handling in batch operations."""
        # Mock some clients to raise exceptions
        mock_client.search_variants.side_effect = [
            [{"_id": "valid1", "rsid": "rs1"}],  # First call succeeds
            Exception("Network error"),  # Second call fails
            [{"_id": "valid2", "rsid": "rs2"}],  # Third call succeeds
        ]

        # This would be called in a hypothetical batch method
        # Since the actual service doesn't have a batch method, we test individual calls
        results = []
        errors = []

        variant_ids = ["rs1", "rs2", "rs3"]
        for variant_id in variant_ids:
            try:
                result = await service.search_variants(variant_id, limit=1)
                results.append(result)
            except Exception as e:
                errors.append(e)

        # Should have 2 successful results and 1 error
        assert len(results) == 2
        assert len(errors) == 1
        assert "Network error" in str(errors[0])

    def test_cache_key_generation(self, service: VariantService) -> None:
        """Test cache key generation logic."""
        # Test the private method directly
        key1 = service._generate_cache_key("search", query="BRCA1", limit=10)
        key2 = service._generate_cache_key("search", query="BRCA1", limit=10)
        key3 = service._generate_cache_key("search", query="CFH", limit=10)

        # Same parameters should generate same key
        assert key1 == key2

        # Different parameters should generate different keys
        assert key1 != key3

        # Keys should contain operation and parameters
        assert "search" in key1
        assert "query:BRCA1" in key1
        assert "limit:10" in key1

    def test_cache_config_handling(
        self,
        mock_client: AsyncMock,
        mock_logger: MagicMock,
    ) -> None:
        """Test cache configuration handling with different config types."""
        # Test with minimal cache config
        minimal_config = CacheConfig(size=50, ttl=600)
        service = VariantService(
            client=mock_client,
            cache_config=minimal_config,
            logger=mock_logger,
        )

        assert service.cache_config.size == 50
        assert service.cache_config.ttl == 600

        # Test with config missing attributes (edge case)
        class MinimalConfig:
            pass

        minimal_config_obj = MinimalConfig()
        service = VariantService(
            client=mock_client,
            cache_config=minimal_config_obj,
            logger=mock_logger,
        )

        # Should use default values when attributes are missing
        assert service.cache_config is minimal_config_obj

    @pytest.mark.asyncio
    async def test_whitespace_query_handling(
        self,
        service: VariantService,
        mock_client: AsyncMock,
        sample_variant_data: dict,
    ) -> None:
        """Test handling of queries with various whitespace."""
        mock_client.search_variants.return_value = [sample_variant_data]

        # Test query with leading/trailing whitespace
        result = await service.search_variants("  CFH  ", limit=10)
        assert result.query == "CFH"

        # Verify client was called with trimmed query
        mock_client.search_variants.assert_called_with("CFH", limit=10)

    @pytest.mark.asyncio
    async def test_service_without_logger(
        self,
        mock_client: AsyncMock,
        cache_config: CacheConfig,
        sample_variant_data: dict,
    ) -> None:
        """Test service operation without logger."""
        # Create service without logger
        service = VariantService(
            client=mock_client,
            cache_config=cache_config,
            logger=None,
        )

        # Mock client to return invalid data that would cause parsing error
        mock_client.search_variants.return_value = [
            sample_variant_data,
            {"invalid": "data"},  # This will cause parsing error
        ]

        # Should handle parsing error gracefully even without logger
        result = await service.search_variants("CFH", limit=10)
        assert len(result.variants) == 1  # Only valid variant should be included

    def test_cache_stats_property(
        self,
        service: VariantService,
    ) -> None:
        """Test cache_stats property."""
        stats = service.cache_stats

        # Should return dictionary with cache statistics
        assert isinstance(stats, dict)
        assert "hits" in stats
        assert "misses" in stats
        assert "hit_rate" in stats
        assert "total_requests" in stats

    @pytest.mark.asyncio
    async def test_cache_ttl_expiration(
        self,
        mock_client: AsyncMock,
        mock_logger: MagicMock,
        sample_variant_data: dict,
    ) -> None:
        """Test cache TTL expiration."""
        # Create service with very short TTL
        cache_config = CacheConfig(
            size=100,
            ttl=60,
            stats_enabled=True,
        )  # 60 second TTL (minimum)
        service = VariantService(mock_client, cache_config, mock_logger)

        # Mock client response
        mock_client.search_variants.return_value = [sample_variant_data]

        # First call
        result1 = await service.search_variants("CFH", limit=10)
        assert not result1.cached

        # Immediate second call should be cached
        result2 = await service.search_variants("CFH", limit=10)
        assert result2.cached

        # For testing purposes, we'll clear the cache instead of waiting for TTL
        await service.clear_cache()

        # Third call should not be cached (cache cleared)
        result3 = await service.search_variants("CFH", limit=10)
        assert not result3.cached

        # Should have made 2 client calls (initial + after cache clear)
        assert mock_client.search_variants.call_count == 2

    @pytest.mark.asyncio
    async def test_error_handling_with_logging(
        self,
        service: VariantService,
        mock_client: AsyncMock,
        mock_logger: MagicMock,
    ) -> None:
        """Test error handling and logging."""
        # Mock client to raise error
        error_message = "Simulated API error"
        mock_client.search_variants.side_effect = LitVarAPIError(error_message)

        # Call should raise error
        with pytest.raises(LitVarAPIError, match=error_message):
            await service.search_variants("CFH", limit=10)

        # Verify error was logged
        mock_logger.error.assert_called()
        log_calls = mock_logger.error.call_args_list
        assert any(error_message in str(call) for call in log_calls)

    @pytest.mark.asyncio
    async def test_response_time_tracking(
        self,
        service: VariantService,
        mock_client: AsyncMock,
        sample_variant_data: dict,
    ) -> None:
        """Test response time tracking."""

        # Mock client with delay
        async def delayed_response(*_args, **_kwargs):
            await asyncio.sleep(0.1)  # 100ms delay
            return [sample_variant_data]

        mock_client.search_variants.side_effect = delayed_response

        result = await service.search_variants("CFH", limit=10)

        # Should track response time
        assert result.search_time_ms >= 100  # At least 100ms due to delay
        assert result.search_time_ms < 500  # Should be reasonable

    @pytest.mark.asyncio
    async def test_empty_results_handling(
        self,
        service: VariantService,
        mock_client: AsyncMock,
    ) -> None:
        """Test handling of empty API responses."""
        # Mock empty responses
        mock_client.search_variants.return_value = []
        mock_client.get_variants_by_gene.return_value = []
        mock_client.get_variant_publications.return_value = []

        # Test empty variant search
        result = await service.search_variants("NONEXISTENT", limit=10)
        assert isinstance(result, VariantSearchResponse)
        assert len(result.variants) == 0
        assert result.total_count == 0

        # Test empty gene variants
        result = await service.search_gene_variants("NONEXISTENT")
        assert isinstance(result, GeneVariantsResponse)
        assert len(result.variants) == 0
        assert result.total_count == 0

        # Test empty publications (canonical id -> resolution skipped, so this
        # exercises the empty-publications path, not the unresolvable path).
        result = await service.get_variant_literature("litvar@rs0000000##")
        assert isinstance(result, PublicationResponse)
        assert len(result.pmids) == 0
        assert result.total_count == 0

    @pytest.mark.asyncio
    async def test_service_cleanup(
        self,
        service: VariantService,
        mock_client: AsyncMock,
        sample_variant_data: dict,
    ) -> None:
        """Test service cleanup and resource management."""
        # Mock client response
        mock_client.search_variants.return_value = [sample_variant_data]

        # Use service and populate cache
        await service.search_variants("CFH", limit=10)
        assert service.cache_stats["total_requests"] > 0

        # Cleanup should clear cache stats (if implemented)
        if hasattr(service, "cleanup"):
            await service.cleanup()
            # Test would verify cleanup behavior

    @pytest.mark.asyncio
    async def test_resolve_rsid_then_get_literature_chain(
        self,
        service: VariantService,
        mock_client: AsyncMock,
    ) -> None:
        """The canonical variant_id from resolve_rsid feeds get_variant_literature
        -- the chain issue #20 broke (a null variant_id could not be forwarded).
        PMIDs are 8 digits so they pass Publication.pmid validation.
        """
        mock_client.sensor_lookup.return_value = {
            "pmids_count": 2,
            "rsid": "rs113993960",
            "link": (
                "https://www.ncbi.nlm.nih.gov/research/litvar2/docsum"
                "?variant=litvar%40rs113993960%23%23"
            ),
            "logo": "x",
        }
        mock_client.search_variants.return_value = [
            {
                "_id": "litvar@rs113993960##",
                "rsid": "rs113993960",
                "gene": ["CFTR"],
                "name": "p.F508del",
                "hgvs": "p.F508del",
                "pmids_count": 2,
            }
        ]
        mock_client.get_variant_publications.return_value = ["37388288", "18022401"]

        resolved = await service.lookup_rsid("rs113993960")
        assert resolved.variant_id == "litvar@rs113993960##"

        lit = await service.get_variant_literature(resolved.variant_id)
        mock_client.get_variant_publications.assert_awaited_once_with(
            "litvar@rs113993960##"
        )
        assert lit.total_count == 2
        assert all(isinstance(p.pmid, str) for p in lit.publications)


class TestValidationDelegation:
    """After DRY #1, both layers raise ValidationError via validation.py."""

    @pytest.fixture
    def cache_config(self) -> CacheConfig:
        """Create test cache config."""
        return CacheConfig(
            size=100,
            ttl=300,
            stats_enabled=True,
            cleanup_interval=60,
        )

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        """Create mock LitVar2 client."""
        client = AsyncMock()
        client.search_variants = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_service_search_empty_query_raises_validation_error(
        self, mock_client: AsyncMock, cache_config
    ) -> None:
        from litvar_link.services.variant_service import VariantService

        service = VariantService(mock_client, cache_config)
        with pytest.raises(ValidationError) as exc:
            await service.search_variants("   ", limit=10)
        assert exc.value.field == "query"
        mock_client.search_variants.assert_not_called()

    @pytest.mark.asyncio
    async def test_client_invalid_rsid_raises_validation_error(self) -> None:
        from litvar_link.api.client import LitVar2Client
        from litvar_link.config import get_api_config

        client = LitVar2Client(config=get_api_config())
        with pytest.raises(ValidationError):
            await client.sensor_lookup("notanrsid")
        await client.close()
