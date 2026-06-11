"""Response models for LitVar-Link API."""

from typing import Any

from pydantic import BaseModel, Field

from .endpoint_specific import (
    AutocompleteVariantItem,
    GeneVariantItem,
    VariantDetailsItem,
)
from .variants import Publication, VariantDetails


class BaseResponse(BaseModel):
    """Base response model with common fields."""

    success: bool = Field(
        default=True,
        description="Whether the request was successful",
    )
    message: str | None = Field(
        default=None,
        description="Optional message or error description",
    )
    timestamp: str | None = Field(
        default=None,
        description="Response timestamp (ISO format)",
    )


class VariantSearchResponse(BaseResponse):
    """Response model for variant search/autocomplete."""

    variants: list[AutocompleteVariantItem] = Field(
        description="List of matching variants",
    )
    total_count: int = Field(description="Total number of matches found")
    query: str = Field(description="Original search query")
    limit: int = Field(description="Number of results requested")
    has_more: bool = Field(description="Whether more results are available")

    # Search metadata
    search_time_ms: float | None = Field(
        default=None,
        description="Search execution time in milliseconds",
    )
    cached: bool = Field(
        default=False,
        description="Whether results were served from cache",
    )


class VariantDetailsResponse(BaseResponse):
    """Response model for variant details."""

    variant: VariantDetailsItem = Field(description="Detailed variant information")
    cached: bool = Field(
        default=False,
        description="Whether results were served from cache",
    )
    last_updated: str | None = Field(
        default=None,
        description="When variant data was last updated",
    )


class PublicationResponse(BaseResponse):
    """Response model for variant publications."""

    variant_id: str = Field(description="Variant identifier")
    publications: list[Publication] = Field(
        description="List of associated publications",
    )
    total_count: int = Field(description="Total number of publications")
    pmid_count: int = Field(description="Number of PubMed publications")
    pmc_count: int = Field(description="Number of PMC publications")

    # Response metadata
    format: str = Field(description="Response format used")
    cached: bool = Field(
        default=False,
        description="Whether results were served from cache",
    )

    @property
    def pmids(self) -> list[str]:
        """Get list of PMIDs."""
        return [pub.pmid for pub in self.publications if pub.pmid]

    @property
    def pmcids(self) -> list[str]:
        """Get list of PMCIDs."""
        return [pub.pmcid for pub in self.publications if pub.pmcid]


class SensorResponse(BaseResponse):
    """Response model for RSID sensor lookup."""

    rsid: str = Field(description="Queried RSID")
    available: bool = Field(description="Whether RSID is available in LitVar2")
    variant_id: str | None = Field(
        default=None,
        description="Associated variant ID if available",
    )
    litvar_url: str | None = Field(default=None, description="Direct URL to LitVar2 page")
    pmids_count: int | None = Field(
        default=None,
        description="Number of associated publications",
    )

    # Additional metadata if available
    gene: list[str] | None = Field(default=None, description="Associated genes")
    variant_name: str | None = Field(default=None, description="Variant name if available")
    search_time_ms: float | None = Field(
        default=None,
        description="Search execution time in milliseconds",
    )
    cached: bool = Field(
        default=False,
        description="Whether results were served from cache",
    )


class GeneVariantsResponse(BaseResponse):
    """Response model for gene variants search."""

    gene: str = Field(description="Queried gene name")
    variants: list[GeneVariantItem] = Field(description="List of variants for the gene")
    total_count: int = Field(description="Total number of variants found")

    # Gene-specific statistics
    pathogenic_count: int = Field(
        default=0,
        description="Number of pathogenic variants",
    )
    benign_count: int = Field(default=0, description="Number of benign variants")
    uncertain_count: int = Field(
        default=0,
        description="Number of variants with uncertain significance",
    )
    total_publications: int = Field(
        default=0,
        description="Total number of publications",
    )

    # Response metadata
    search_time_ms: float | None = Field(
        default=None,
        description="Search execution time in milliseconds",
    )
    cached: bool = Field(
        default=False,
        description="Whether results were served from cache",
    )

    @property
    def variant_types(self) -> dict[str, int]:
        """Get count of variants by type."""
        type_counts: dict[str, int] = {}

        for _variant in self.variants:
            # GeneVariantItem doesn't have clinical_significance field
            # All gene variants are considered "unknown" since we don't have clinical data
            type_counts["unknown"] = type_counts.get("unknown", 0) + 1

        return type_counts


class BatchVariantResponse(BaseResponse):
    """Response model for batch variant operations."""

    variants: list[VariantDetails] = Field(description="List of variant details")
    found_count: int = Field(description="Number of variants found")
    not_found: list[str] = Field(description="List of variant IDs not found")

    # Batch metadata
    requested_count: int = Field(description="Number of variants requested")
    include_publications: bool = Field(description="Whether publications were included")
    format: str = Field(description="Response format")


class CacheStatsResponse(BaseResponse):
    """Response model for cache statistics."""

    model_config = {"populate_by_name": True}

    total_size: int = Field(description="Total number of cached items")
    hit_count: int = Field(alias="hits", description="Number of cache hits")
    miss_count: int = Field(alias="misses", description="Number of cache misses")
    hit_rate: float = Field(description="Cache hit rate (0.0-1.0)")
    total_requests: int = Field(default=0, description="Total number of requests")

    # Memory usage
    memory_usage_mb: float | None = Field(
        default=None,
        description="Approximate memory usage in MB",
    )
    max_size: int | None = Field(default=None, description="Maximum cache size")

    # TTL information
    average_ttl: float | None = Field(
        default=None,
        description="Average TTL of cached items in seconds",
    )
    expired_count: int = Field(description="Number of expired items")


class HealthResponse(BaseResponse):
    """Response model for health checks."""

    status: str = Field(description="Overall service status")
    version: str = Field(description="Service version")
    uptime_seconds: float = Field(description="Service uptime in seconds")

    # Component health
    litvar_api_status: str = Field(description="LitVar2 API connectivity status")
    cache_status: str = Field(description="Cache system status")
    database_status: str | None = Field(
        default=None,
        description="Database status if applicable",
    )

    # API statistics
    api_stats: dict[str, Any] | None = Field(
        default=None,
        description="API client statistics",
    )

    # Performance metrics
    requests_per_minute: float | None = Field(
        default=None,
        description="Recent request rate",
    )
    average_response_time_ms: float | None = Field(
        default=None,
        description="Average response time",
    )
    error_rate: float | None = Field(default=None, description="Recent error rate")

    # System resources
    memory_usage_percent: float | None = Field(
        default=None,
        description="Memory usage percentage",
    )
    cpu_usage_percent: float | None = Field(default=None, description="CPU usage percentage")


class ErrorResponse(BaseResponse):
    """Response model for API errors."""

    success: bool = Field(default=False, description="Always false for error responses")
    error_code: str = Field(description="Machine-readable error code")
    error_type: str = Field(description="Error category")
    details: dict[str, Any] | None = Field(
        default=None,
        description="Additional error details",
    )

    # Request context
    request_id: str | None = Field(default=None, description="Unique request identifier")
    endpoint: str | None = Field(default=None, description="API endpoint that failed")

    # Retry information
    retryable: bool = Field(
        default=False,
        description="Whether the request can be retried",
    )
    retry_after_seconds: int | None = Field(
        default=None,
        description="Recommended retry delay",
    )


class ValidationErrorDetail(BaseModel):
    """Detailed validation error information."""

    field: str = Field(description="Field that failed validation")
    message: str = Field(description="Validation error message")
    invalid_value: Any = Field(description="The invalid value provided")
    expected_type: str | None = Field(default=None, description="Expected data type")


class ValidationErrorResponse(ErrorResponse):
    """Response model for validation errors."""

    error_code: str = Field(
        default="VALIDATION_ERROR",
        description="Always VALIDATION_ERROR",
    )
    validation_errors: list[ValidationErrorDetail] = Field(
        description="List of field validation errors",
    )
