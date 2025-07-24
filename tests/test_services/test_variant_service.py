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

        # Due to caching, client should only be called once
        assert mock_client.search_variants.call_count == 1

    @pytest.mark.asyncio
    async def test_cache_ttl_expiration(
        self,
        mock_client: AsyncMock,
        mock_logger: MagicMock,
        sample_variant_data: dict,
    ) -> None:
        """Test cache TTL expiration."""
        # Create service with very short TTL
        cache_config = CacheConfig(size=100, ttl=1, stats_enabled=True)  # 1 second TTL
        service = VariantService(mock_client, cache_config, mock_logger)

        # Mock client response
        mock_client.search_variants.return_value = [sample_variant_data]

        # First call
        result1 = await service.search_variants("CFH", limit=10)
        assert not result1.cached

        # Immediate second call should be cached
        result2 = await service.search_variants("CFH", limit=10)
        assert result2.cached

        # Wait for TTL to expire
        await asyncio.sleep(1.1)

        # Third call should not be cached (TTL expired)
        result3 = await service.search_variants("CFH", limit=10)
        assert not result3.cached

        # Should have made 2 client calls (initial + after TTL expiry)
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

        # Test empty publications
        result = await service.get_variant_literature("nonexistent_id")
        assert isinstance(result, PublicationResponse)
        assert len(result.pmids) == 0
        assert result.total_count == 0

    def test_cache_key_generation(
        self,
        service: VariantService,
        mock_client: AsyncMock,  # noqa: ARG002
        mock_logger: MagicMock,  # noqa: ARG002
    ) -> None:
        """Test cache key generation for different methods."""
        # Access private method for testing
        key1 = service._generate_cache_key("search", query="CFH", limit=10)
        key2 = service._generate_cache_key("search", query="CFH", limit=5)
        key3 = service._generate_cache_key("search", query="BRCA1", limit=10)
        key4 = service._generate_cache_key("gene", gene_name="CFH")

        # Keys should be different for different parameters
        assert key1 != key2  # Different limit
        assert key1 != key3  # Different query
        assert key1 != key4  # Different method

        # Same parameters should generate same key
        key1_repeat = service._generate_cache_key("search", query="CFH", limit=10)
        assert key1 == key1_repeat

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
