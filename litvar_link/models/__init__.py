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
    # Endpoint-specific models
    "AutocompleteVariantItem",
    # Response models
    "BaseResponse",
    "CacheStatsResponse",
    "ClinicalSignificance",
    "GeneVariantItem",
    "GeneVariantsRequest",
    "GeneVariantsResponse",
    "HealthResponse",
    "Publication",
    "PublicationRequest",
    "PublicationResponse",
    "PublicationsItem",
    "SensorItem",
    "SensorRequest",
    "SensorResponse",
    # Core models
    "Variant",
    "VariantDetails",
    "VariantDetailsItem",
    "VariantDetailsRequest",
    "VariantDetailsResponse",
    # Request models
    "VariantSearchRequest",
    "VariantSearchResponse",
]
