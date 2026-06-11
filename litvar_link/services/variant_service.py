"""Variant service with caching and business logic."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any, TypeVar, cast

from litvar_link.exceptions import ValidationError
from litvar_link.logging_config import log_error_with_context
from litvar_link.models import (
    GeneVariantsResponse,
    PublicationResponse,
    SensorResponse,
    VariantDetails,
    VariantDetailsResponse,
    VariantSearchResponse,
)
from litvar_link.services.cache_hits import hits_before, was_cache_hit
from litvar_link.utils.caching import create_service_cache_decorator
from litvar_link.validation import (
    validate_gene_name,
    validate_limit,
    validate_query,
    validate_rsid,
)

if TYPE_CHECKING:
    from structlog.typing import FilteringBoundLogger

    from litvar_link.api.client import LitVar2Client
    from litvar_link.config import CacheConfig

_ModelT = TypeVar("_ModelT")

_PATHOGENIC = ("pathogenic", "likely pathogenic")
_BENIGN = ("benign", "likely benign")


def _count_clinical_significance(variants: list[Any]) -> tuple[int, int, int]:
    """Tally ``(pathogenic, benign, uncertain)`` counts across gene variants.

    A variant with no ``data_clinical_significance`` (or empty) counts as
    uncertain; otherwise the first matching pathogenic/benign bucket wins, else
    uncertain.
    """
    pathogenic = benign = uncertain = 0
    for variant in variants:
        sigs = getattr(variant, "data_clinical_significance", None)
        if not sigs:
            uncertain += 1
        elif any(sig in _PATHOGENIC for sig in sigs):
            pathogenic += 1
        elif any(sig in _BENIGN for sig in sigs):
            benign += 1
        else:
            uncertain += 1
    return pathogenic, benign, uncertain


class VariantService:
    """Service for variant operations with caching and business logic."""

    def __init__(
        self,
        client: LitVar2Client,
        cache_config: CacheConfig,
        logger: FilteringBoundLogger | None = None,
    ) -> None:
        """Initialize variant service.

        Args:
            client: LitVar2 API client
            cache_config: Cache configuration
            logger: Optional logger instance
        """
        self.client = client
        self.cache_config = cache_config
        self.logger = logger

        # Initialize centralized cache manager
        self.cache = create_service_cache_decorator(logger)

        # Apply caching decorators to methods
        self._setup_cached_methods()

    def _generate_cache_key(self, operation: str, **kwargs: Any) -> str:
        """Generate cache key for operation.

        Args:
            operation: Operation name
            **kwargs: Parameters for cache key

        Returns:
            Cache key string
        """
        parts = [operation]
        for key, value in sorted(kwargs.items()):
            parts.append(f"{key}:{value}")
        return ":".join(parts)

    @property
    def cache_stats(self) -> dict[str, Any]:
        """Get comprehensive cache statistics."""
        return self.cache.cache_stats

    def _setup_cached_methods(self) -> None:
        """Set up cached methods using the cache manager."""
        # Use config values or defaults for search variants
        search_maxsize = self.cache_config.size if hasattr(self.cache_config, "size") else 256
        search_ttl = self.cache_config.ttl if hasattr(self.cache_config, "ttl") else 3600

        self._cached_search_variants = self.cache.cached(
            maxsize=search_maxsize,
            ttl=search_ttl,
            key_pattern="search_variants",
        )(self._search_variants_impl)

        self._cached_get_variant_details = self.cache.cached(
            maxsize=500,
            ttl=7200,
            key_pattern="variant_details",
        )(self._get_variant_details_impl)

        self._cached_get_variant_publications = self.cache.cached(
            maxsize=500,
            ttl=3600,
            key_pattern="variant_publications",
        )(self._get_variant_publications_impl)

        self._cached_sensor_lookup = self.cache.cached(
            maxsize=1000,
            ttl=86400,
            key_pattern="sensor_lookup",
        )(self._sensor_lookup_impl)

        self._cached_get_variants_by_gene = self.cache.cached(
            maxsize=200,
            ttl=3600,
            key_pattern="gene_variants",
        )(self._get_variants_by_gene_impl)

    async def _search_variants_impl(
        self,
        query: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Search variants implementation."""
        return await self.client.search_variants(query, limit=limit)

    async def _get_variant_details_impl(self, variant_id: str) -> dict[str, Any]:
        """Get variant details implementation."""
        return await self.client.get_variant_details(variant_id)

    async def _get_variant_publications_impl(self, variant_id: str) -> list[str]:
        """Get variant publications implementation."""
        return await self.client.get_variant_publications(variant_id)

    async def _sensor_lookup_impl(self, rsid: str) -> dict[str, Any] | None:
        """RSID sensor lookup implementation."""
        return await self.client.sensor_lookup(rsid)

    async def _get_variants_by_gene_impl(
        self,
        gene_name: str,
    ) -> list[dict[str, Any]]:
        """Get variants by gene implementation."""
        return await self.client.get_variants_by_gene(gene_name)

    def _parse_items(
        self,
        data_list: list[dict[str, Any]],
        model_cls: type[_ModelT],
    ) -> list[_ModelT]:
        """Parse raw rows into ``model_cls`` instances, skipping bad rows.

        Rows that fail validation are logged (with context) and dropped rather
        than aborting the whole response. Shared by the autocomplete-search and
        gene-search parse paths.
        """
        parsed: list[_ModelT] = []
        for data in data_list:
            try:
                parsed.append(model_cls(**data))
            except Exception as e:  # per-row resilience: skip bad rows
                if self.logger:
                    log_error_with_context(
                        self.logger,
                        e,
                        "variant_parsing",
                        {"variant_data": data},
                    )
        return parsed

    async def search_variants(
        self,
        query: str,
        limit: int = 10,
    ) -> VariantSearchResponse:
        """Search variants with caching and validation.

        Args:
            query: Search query
            limit: Maximum number of results

        Returns:
            Variant search response

        Raises:
            ValidationError: For invalid input parameters
            LitVarAPIError: For API-related errors
        """
        query = validate_query(query)
        limit = validate_limit(limit)

        try:
            start_time = time.time()

            initial_hits = hits_before(self._cached_search_variants)
            variant_data = await self._cached_search_variants(query, limit)
            cached = was_cache_hit(self._cached_search_variants, before=initial_hits)

            # Parse variants using the endpoint-specific model
            from litvar_link.models.endpoint_specific import AutocompleteVariantItem

            variants = self._parse_items(variant_data, AutocompleteVariantItem)

            search_time = (time.time() - start_time) * 1000

            return VariantSearchResponse(
                variants=variants,
                total_count=len(variants),
                query=query,
                limit=limit,
                has_more=len(variants) == limit,
                search_time_ms=search_time,
                cached=cached,
            )

        except Exception as e:
            if self.logger:
                log_error_with_context(
                    self.logger,
                    e,
                    "search_variants",
                    {"query": query, "limit": limit},
                )
            raise

    async def get_variant_summary(self, variant_id: str) -> VariantDetailsResponse:
        """Get detailed variant information.

        Args:
            variant_id: Unique variant identifier

        Returns:
            Variant details response

        Raises:
            ValidationError: For invalid input parameters
            LitVarAPIError: For API-related errors
        """
        if not variant_id or not variant_id.strip():
            msg = "Variant ID cannot be empty"
            raise ValidationError(msg, field="variant_id")

        variant_id = variant_id.strip()
        try:
            initial_hits = hits_before(self._cached_get_variant_details)
            variant_data = await self._cached_get_variant_details(variant_id)
            cached = was_cache_hit(self._cached_get_variant_details, before=initial_hits)

            # Parse variant details
            variant = VariantDetails(**variant_data)

            return VariantDetailsResponse(
                # VariantDetails/VariantDetailsItem reconciliation is deferred to P3.
                variant=cast("Any", variant),
                cached=cached,
            )

        except Exception as e:
            if self.logger:
                log_error_with_context(
                    self.logger,
                    e,
                    "get_variant_summary",
                    {"variant_id": variant_id},
                )
            raise

    async def get_variant_literature(self, variant_id: str) -> PublicationResponse:
        """Get publications associated with a variant.

        Args:
            variant_id: Unique variant identifier

        Returns:
            Publication response

        Raises:
            ValidationError: For invalid input parameters
            LitVarAPIError: For API-related errors
        """
        if not variant_id or not variant_id.strip():
            msg = "Variant ID cannot be empty"
            raise ValidationError(msg, field="variant_id")

        variant_id = variant_id.strip()
        try:
            initial_hits = hits_before(self._cached_get_variant_publications)
            pmids = await self._cached_get_variant_publications(variant_id)
            cached = was_cache_hit(
                self._cached_get_variant_publications,
                before=initial_hits,
            )

            # Create publication objects (simplified for now)
            from litvar_link.models.variants import Publication

            publications = [Publication(pmid=pmid) for pmid in pmids if pmid]

            return PublicationResponse(
                variant_id=variant_id,
                publications=publications,
                total_count=len(publications),
                pmid_count=len(publications),
                pmc_count=0,  # Not available from this endpoint
                format="json",
                cached=cached,
            )

        except Exception as e:
            if self.logger:
                log_error_with_context(
                    self.logger,
                    e,
                    "get_variant_literature",
                    {"variant_id": variant_id},
                )
            raise

    async def lookup_rsid(self, rsid: str) -> SensorResponse:
        """Check if RSID is available in LitVar2.

        Args:
            rsid: Reference SNP ID

        Returns:
            Sensor response

        Raises:
            ValidationError: For invalid input parameters
            LitVarAPIError: For API-related errors
        """
        rsid = validate_rsid(rsid)

        try:
            initial_hits = hits_before(self._cached_sensor_lookup)
            sensor_data = await self._cached_sensor_lookup(rsid)
            cached = was_cache_hit(self._cached_sensor_lookup, before=initial_hits)

            # Parse sensor response - handle None case
            if sensor_data is None:
                return SensorResponse(
                    rsid=rsid,
                    available=False,
                    variant_id=None,
                    litvar_url=None,
                    pmids_count=None,
                    gene=None,
                    variant_name=None,
                    cached=cached,
                )

            return SensorResponse(
                rsid=rsid,
                available=True,
                variant_id=sensor_data.get("variant_id"),
                litvar_url=sensor_data.get("litvar_url"),
                pmids_count=sensor_data.get("pmids_count"),
                gene=sensor_data.get("gene"),
                variant_name=sensor_data.get("variant_name"),
                cached=cached,
            )

        except Exception as e:
            if self.logger:
                log_error_with_context(
                    self.logger,
                    e,
                    "lookup_rsid",
                    {"rsid": rsid},
                )
            raise

    async def search_gene_variants(self, gene_name: str) -> GeneVariantsResponse:
        """Get all variants for a specific gene.

        Args:
            gene_name: Gene symbol

        Returns:
            Gene variants response

        Raises:
            ValidationError: For invalid input parameters
            LitVarAPIError: For API-related errors
        """
        gene_name = validate_gene_name(gene_name)
        try:
            initial_hits = hits_before(self._cached_get_variants_by_gene)
            variant_data = await self._cached_get_variants_by_gene(gene_name)
            cached = was_cache_hit(
                self._cached_get_variants_by_gene,
                before=initial_hits,
            )

            # Parse variants using the endpoint-specific model
            from litvar_link.models.endpoint_specific import GeneVariantItem

            variants = self._parse_items(variant_data, GeneVariantItem)

            pathogenic_count, benign_count, uncertain_count = _count_clinical_significance(
                variants,
            )

            # Calculate total publications (sum of pmids_count)
            total_publications = sum(
                getattr(variant, "pmids_count", 0) or 0 for variant in variants
            )

            return GeneVariantsResponse(
                gene=gene_name,
                variants=variants,
                total_count=len(variants),
                pathogenic_count=pathogenic_count,
                benign_count=benign_count,
                uncertain_count=uncertain_count,
                total_publications=total_publications,
                cached=cached,
            )

        except Exception as e:
            if self.logger:
                log_error_with_context(
                    self.logger,
                    e,
                    "search_gene_variants",
                    {"gene_name": gene_name},
                )
            raise

    async def clear_cache(self, pattern: str | None = None) -> dict[str, int]:
        """Clear service cache using centralized cache manager.

        Args:
            pattern: Optional pattern to match cache keys

        Returns:
            Dictionary with cleared cache statistics
        """
        return self.cache.clear_all_caches(pattern)

    def get_cache_info(self) -> dict[str, Any]:
        """Get detailed cache information for all cached methods.

        Returns:
            Dictionary with cache information for each cached method
        """
        return self.cache.get_cache_info()
