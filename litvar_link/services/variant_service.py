"""Variant service with caching and business logic."""

from __future__ import annotations

import time
from typing import Any

from async_lru import alru_cache
from structlog.typing import FilteringBoundLogger

from ..api.client import LitVar2Client
from ..config import CacheConfig
from ..exceptions import ValidationError
from ..logging_config import log_cache_operation, log_error_with_context
from ..models import (
    GeneVariantsResponse,
    PublicationResponse,
    SensorResponse,
    VariantDetails,
    VariantDetailsResponse,
    VariantSearchResponse,
)


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
        self._cache_stats = {"hits": 0, "misses": 0}

    @property
    def cache_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        total_requests = self._cache_stats["hits"] + self._cache_stats["misses"]
        hit_rate = (
            self._cache_stats["hits"] / total_requests if total_requests > 0 else 0.0
        )

        return {
            "hits": self._cache_stats["hits"],
            "misses": self._cache_stats["misses"],
            "hit_rate": hit_rate,
            "total_requests": total_requests,
        }

    def _log_cache_hit(self, key: str) -> None:
        """Log cache hit."""
        self._cache_stats["hits"] += 1
        if self.logger:
            log_cache_operation(self.logger, "hit", key, hit=True)

    def _log_cache_miss(self, key: str) -> None:
        """Log cache miss."""
        self._cache_stats["misses"] += 1
        if self.logger:
            log_cache_operation(self.logger, "miss", key, hit=False)

    @alru_cache(maxsize=1000, ttl=3600)  # 1 hour TTL
    async def _cached_search_variants(
        self,
        query: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Cached variant search."""
        return await self.client.search_variants(query, limit)

    @alru_cache(maxsize=500, ttl=7200)  # 2 hour TTL for variant details
    async def _cached_get_variant_details(self, variant_id: str) -> dict[str, Any]:
        """Cached variant details retrieval."""
        return await self.client.get_variant_details(variant_id)

    @alru_cache(maxsize=500, ttl=3600)  # 1 hour TTL for publications
    async def _cached_get_variant_publications(self, variant_id: str) -> list[str]:
        """Cached variant publications retrieval."""
        return await self.client.get_variant_publications(variant_id)

    @alru_cache(maxsize=1000, ttl=86400)  # 24 hour TTL for sensor data
    async def _cached_sensor_lookup(self, rsid: str) -> dict[str, Any]:
        """Cached RSID sensor lookup."""
        return await self.client.sensor_lookup(rsid)

    @alru_cache(maxsize=200, ttl=3600)  # 1 hour TTL for gene variants
    async def _cached_get_variants_by_gene(
        self,
        gene_name: str,
    ) -> list[dict[str, Any]]:
        """Cached gene variants retrieval."""
        return await self.client.get_variants_by_gene(gene_name)

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
        # Input validation
        if not query or not query.strip():
            raise ValidationError("Query cannot be empty", field="query")

        if limit < 1 or limit > 100:
            raise ValidationError("Limit must be between 1 and 100", field="limit")

        query = query.strip()
        cache_key = f"search:{query}:{limit}"

        try:
            start_time = time.time()

            # Check if result is cached
            cache_info = self._cached_search_variants.cache_info()
            initial_hits = cache_info.hits

            # Make cached call
            variant_data = await self._cached_search_variants(query, limit)

            # Check if cache was hit
            new_cache_info = self._cached_search_variants.cache_info()
            cached = new_cache_info.hits > initial_hits

            if cached:
                self._log_cache_hit(cache_key)
            else:
                self._log_cache_miss(cache_key)

            # Parse variants using the endpoint-specific model
            from ..models.endpoint_specific import AutocompleteVariantItem

            variants = []
            for data in variant_data:
                try:
                    variant = AutocompleteVariantItem(**data)
                    variants.append(variant)
                except Exception as e:
                    if self.logger:
                        log_error_with_context(
                            self.logger,
                            e,
                            "variant_parsing",
                            {"variant_data": data},
                        )
                    continue

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
            raise ValidationError("Variant ID cannot be empty", field="variant_id")

        variant_id = variant_id.strip()
        cache_key = f"details:{variant_id}"

        try:
            # Check if result is cached
            cache_info = self._cached_get_variant_details.cache_info()
            initial_hits = cache_info.hits

            # Make cached call
            variant_data = await self._cached_get_variant_details(variant_id)

            # Check if cache was hit
            new_cache_info = self._cached_get_variant_details.cache_info()
            cached = new_cache_info.hits > initial_hits

            if cached:
                self._log_cache_hit(cache_key)
            else:
                self._log_cache_miss(cache_key)

            # Parse variant details
            variant = VariantDetails(**variant_data)

            return VariantDetailsResponse(
                variant=variant,
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
            raise ValidationError("Variant ID cannot be empty", field="variant_id")

        variant_id = variant_id.strip()
        cache_key = f"publications:{variant_id}"

        try:
            # Check if result is cached
            cache_info = self._cached_get_variant_publications.cache_info()
            initial_hits = cache_info.hits

            # Make cached call
            pmids = await self._cached_get_variant_publications(variant_id)

            # Check if cache was hit
            new_cache_info = self._cached_get_variant_publications.cache_info()
            cached = new_cache_info.hits > initial_hits

            if cached:
                self._log_cache_hit(cache_key)
            else:
                self._log_cache_miss(cache_key)

            # Create publication objects (simplified for now)
            from ..models.variants import Publication

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
        if not rsid or not rsid.strip():
            raise ValidationError("RSID cannot be empty", field="rsid")

        rsid = rsid.strip().lower()

        # Validate RSID format
        if not rsid.startswith("rs") or not rsid[2:].isdigit():
            raise ValidationError("Invalid RSID format", field="rsid")

        cache_key = f"sensor:{rsid}"

        try:
            # Check if result is cached
            cache_info = self._cached_sensor_lookup.cache_info()
            initial_hits = cache_info.hits

            # Make cached call
            sensor_data = await self._cached_sensor_lookup(rsid)

            # Check if cache was hit
            new_cache_info = self._cached_sensor_lookup.cache_info()
            cached = new_cache_info.hits > initial_hits

            if cached:
                self._log_cache_hit(cache_key)
            else:
                self._log_cache_miss(cache_key)

            # Parse sensor response
            return SensorResponse(
                rsid=rsid,
                available=bool(sensor_data),  # If we get data, it's available
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
        if not gene_name or not gene_name.strip():
            raise ValidationError("Gene name cannot be empty", field="gene_name")

        gene_name = gene_name.strip().upper()
        cache_key = f"gene_variants:{gene_name}"

        try:
            # Check if result is cached
            cache_info = self._cached_get_variants_by_gene.cache_info()
            initial_hits = cache_info.hits

            # Make cached call
            variant_data = await self._cached_get_variants_by_gene(gene_name)

            # Check if cache was hit
            new_cache_info = self._cached_get_variants_by_gene.cache_info()
            cached = new_cache_info.hits > initial_hits

            if cached:
                self._log_cache_hit(cache_key)
            else:
                self._log_cache_miss(cache_key)

            # Parse variants using the endpoint-specific model
            from ..models.endpoint_specific import GeneVariantItem

            variants = []
            for data in variant_data:
                try:
                    variant = GeneVariantItem(**data)
                    variants.append(variant)
                except Exception as e:
                    if self.logger:
                        log_error_with_context(
                            self.logger,
                            e,
                            "variant_parsing",
                            {"variant_data": data},
                        )
                    continue

            # Gene variants endpoint doesn't include clinical significance data
            # So we can't calculate pathogenic/benign statistics accurately
            # All variants are considered uncertain since we don't have the clinical data  # noqa: E501
            pathogenic_count = 0
            benign_count = 0
            uncertain_count = len(variants)

            return GeneVariantsResponse(
                gene_name=gene_name,
                variants=variants,
                total_count=len(variants),
                pathogenic_count=pathogenic_count,
                benign_count=benign_count,
                uncertain_count=uncertain_count,
                sort_by="pmids_count",
                sort_order="desc",
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
        """Clear service cache.

        Args:
            pattern: Optional pattern to match cache keys

        Returns:
            Dictionary with cleared cache statistics
        """
        cleared_count = 0

        # Clear all caches (since async_lru doesn't support pattern matching)
        caches = [
            self._cached_search_variants,
            self._cached_get_variant_details,
            self._cached_get_variant_publications,
            self._cached_sensor_lookup,
            self._cached_get_variants_by_gene,
        ]

        for cache in caches:
            info_before = cache.cache_info()
            cache.cache_clear()
            cleared_count += info_before.currsize

        if self.logger:
            log_cache_operation(
                self.logger,
                "clear",
                pattern or "all",
                size=cleared_count,
            )

        return {"cleared_count": cleared_count}
