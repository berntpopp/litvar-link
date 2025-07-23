"""Data models for LitVar-Link."""

from .endpoint_specific import (
    AutocompleteVariantItem,
    GeneVariantItem,
    PublicationsItem,
    SensorItem,
    VariantDetailsItem,
)
from .requests import (
    GeneVariantsRequest,
    PublicationRequest,
    SensorRequest,
    VariantDetailsRequest,
    VariantSearchRequest,
)
from .responses import (
    BaseResponse,
    CacheStatsResponse,
    GeneVariantsResponse,
    HealthResponse,
    PublicationResponse,
    SensorResponse,
    VariantDetailsResponse,
    VariantSearchResponse,
)
from .variants import ClinicalSignificance, Publication, Variant, VariantDetails

__all__ = [
    # Core models
    "Variant",
    "VariantDetails",
    "Publication",
    "ClinicalSignificance",
    # Endpoint-specific models
    "AutocompleteVariantItem",
    "GeneVariantItem",
    "PublicationsItem",
    "SensorItem",
    "VariantDetailsItem",
    # Request models
    "VariantSearchRequest",
    "VariantDetailsRequest",
    "PublicationRequest",
    "SensorRequest",
    "GeneVariantsRequest",
    # Response models
    "BaseResponse",
    "CacheStatsResponse",
    "GeneVariantsResponse",
    "HealthResponse",
    "PublicationResponse",
    "SensorResponse",
    "VariantDetailsResponse",
    "VariantSearchResponse",
]
