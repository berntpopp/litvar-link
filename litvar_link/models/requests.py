"""Request models for LitVar-Link API."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class VariantSearchRequest(BaseModel):
    """Request model for variant search/autocomplete."""

    query: str = Field(
        description="Search query (variant name, gene, RSID, etc.)",
    )
    limit: int = Field(
        default=10,
        description="Maximum number of results to return",
    )

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        """Clean and validate search query."""
        # Strip whitespace and normalize
        v = v.strip()
        if not v:
            msg = "Query cannot be empty"
            raise ValueError(msg)

        if len(v) > 100:
            msg = "Query too long"
            raise ValueError(msg)

        # Basic sanitization - remove potential harmful characters
        # Note: ">" is allowed for genetic variant notation like "c.317-1G>A"
        dangerous_chars = ["<", "&", '"', ";"]
        for char in dangerous_chars:
            if char in v:
                msg = f"Query contains invalid character: {char}"
                raise ValueError(msg)

        return v

    @field_validator("limit")
    @classmethod
    def validate_limit(cls, v: int) -> int:
        """Validate limit range."""
        if v < 1 or v > 100:
            msg = "Limit must be between 1 and 100"
            raise ValueError(msg)
        return v


class VariantDetailsRequest(BaseModel):
    """Request model for variant details."""

    variant_id: str = Field(
        description="Unique variant identifier",
    )

    @field_validator("variant_id")
    @classmethod
    def validate_variant_id(cls, v: str) -> str:
        """Validate variant ID format."""
        v = v.strip()
        if not v:
            msg = "Variant ID cannot be empty"
            raise ValueError(msg)
        return v


class PublicationRequest(BaseModel):
    """Request model for variant publications."""

    variant_id: str = Field(
        description="Unique variant identifier",
    )
    format: Literal["json", "pmid_list", "detailed"] | None = Field(
        default="json",
        description="Response format",
    )
    limit: int | None = Field(
        default=None,
        ge=1,
        le=1000,
        description="Maximum number of publications to return",
    )

    @field_validator("variant_id")
    @classmethod
    def validate_variant_id(cls, v: str) -> str:
        """Validate variant ID format."""
        v = v.strip()
        if not v:
            msg = "Variant ID cannot be empty"
            raise ValueError(msg)
        return v


class SensorRequest(BaseModel):
    """Request model for RSID sensor lookup."""

    rsid: str = Field(
        description="Reference SNP ID (e.g., rs1061170)",
    )

    @field_validator("rsid")
    @classmethod
    def validate_rsid(cls, v: str) -> str:
        """Validate RSID format."""
        v = v.strip()

        if not v:
            msg = "Invalid RSID format"
            raise ValueError(msg)

        if not v.startswith("rs"):
            msg = "Invalid RSID format"
            raise ValueError(msg)

        numeric_part = v[2:]
        if not numeric_part or not numeric_part.isdigit():
            msg = "Invalid RSID format"
            raise ValueError(msg)

        if len(numeric_part) < 1 or len(numeric_part) > 15:
            msg = "Invalid RSID format"
            raise ValueError(msg)

        return v


class GeneVariantsRequest(BaseModel):
    """Request model for gene variants search."""

    gene_name: str = Field(
        description="Gene symbol (e.g., CFH, BRCA1)",
    )
    limit: int | None = Field(
        default=None,
        ge=1,
        le=1000,
        description="Maximum number of variants to return",
    )
    sort_by: Literal["pmids_count", "name", "rsid"] | None = Field(
        default="pmids_count",
        description="Sort results by field",
    )
    sort_order: Literal["asc", "desc"] | None = Field(
        default="desc",
        description="Sort order",
    )

    @field_validator("gene_name")
    @classmethod
    def validate_gene_name(cls, v: str) -> str:
        """Validate gene name."""
        v = v.strip()

        if not v:
            msg = "Gene name cannot be empty"
            raise ValueError(msg)

        # Basic gene symbol validation
        if not v.replace("-", "").replace("_", "").isalnum():
            msg = "Gene name contains invalid characters"
            raise ValueError(msg)

        # Common gene symbol patterns
        if len(v) > 50:
            msg = "Gene name too long"
            raise ValueError(msg)

        return v


class BatchVariantRequest(BaseModel):
    """Request model for batch variant operations."""

    variant_ids: list[str] = Field(
        min_length=1,
        max_length=100,
        description="List of variant identifiers",
    )
    include_publications: bool = Field(
        default=False,
        description="Include publication data for each variant",
    )
    format: Literal["json", "csv", "tsv"] | None = Field(
        default="json",
        description="Response format",
    )

    @field_validator("variant_ids")
    @classmethod
    def validate_variant_ids(cls, v: list[str]) -> list[str]:
        """Validate list of variant IDs."""
        if not v:
            msg = "At least one variant ID is required"
            raise ValueError(msg)

        # Remove duplicates while preserving order
        seen = set()
        unique_ids = []

        for variant_id in v:
            variant_id = variant_id.strip()
            if not variant_id:
                continue
            if variant_id not in seen:
                unique_ids.append(variant_id)
                seen.add(variant_id)

        if not unique_ids:
            msg = "No valid variant IDs provided"
            raise ValueError(msg)

        if len(unique_ids) > 100:
            msg = "Maximum 100 variant IDs allowed per request"
            raise ValueError(msg)

        return unique_ids


class CacheRequest(BaseModel):
    """Request model for cache operations."""

    operation: Literal["clear", "stats", "warm"] = Field(
        description="Cache operation to perform",
    )
    keys: list[str] | None = Field(
        default=None,
        description="Specific cache keys to operate on (for selective operations)",
    )

    @field_validator("keys")
    @classmethod
    def validate_keys(cls, v: list[str] | None) -> list[str] | None:
        """Validate cache keys."""
        if v is None:
            return v

        # Remove empty keys
        valid_keys = [key.strip() for key in v if key.strip()]
        return valid_keys if valid_keys else None
