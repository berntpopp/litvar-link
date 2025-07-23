"""Request models for LitVar-Link API."""

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class VariantSearchRequest(BaseModel):
    """Request model for variant search/autocomplete."""

    query: str = Field(
        min_length=1,
        max_length=100,
        description="Search query (variant name, gene, RSID, etc.)",
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of results to return",
    )

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        """Clean and validate search query."""
        # Strip whitespace and normalize
        v = v.strip()
        if not v:
            raise ValueError("Query cannot be empty")

        # Basic sanitization - remove potential harmful characters
        # Note: ">" is allowed for genetic variant notation like "c.317-1G>A"
        dangerous_chars = ["<", "&", '"', ";"]
        for char in dangerous_chars:
            if char in v:
                raise ValueError(f"Query contains invalid character: {char}")

        return v


class VariantDetailsRequest(BaseModel):
    """Request model for variant details."""

    variant_id: str = Field(
        min_length=1,
        max_length=50,
        description="Unique variant identifier",
    )

    @field_validator("variant_id")
    @classmethod
    def validate_variant_id(cls, v: str) -> str:
        """Validate variant ID format."""
        v = v.strip()
        if not v:
            raise ValueError("Variant ID cannot be empty")
        return v


class PublicationRequest(BaseModel):
    """Request model for variant publications."""

    variant_id: str = Field(
        min_length=1,
        max_length=50,
        description="Unique variant identifier",
    )
    format: Optional[Literal["json", "pmid_list", "detailed"]] = Field(
        default="json",
        description="Response format",
    )
    limit: Optional[int] = Field(
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
            raise ValueError("Variant ID cannot be empty")
        return v


class SensorRequest(BaseModel):
    """Request model for RSID sensor lookup."""

    rsid: str = Field(
        min_length=3,
        max_length=20,
        description="Reference SNP ID (e.g., rs1061170)",
    )

    @field_validator("rsid")
    @classmethod
    def validate_rsid(cls, v: str) -> str:
        """Validate RSID format."""
        v = v.strip().lower()

        if not v.startswith("rs"):
            raise ValueError("RSID must start with 'rs'")

        numeric_part = v[2:]
        if not numeric_part.isdigit():
            raise ValueError("RSID must have numeric part after 'rs'")

        if len(numeric_part) < 1 or len(numeric_part) > 15:
            raise ValueError("RSID numeric part must be 1-15 digits")

        return v


class GeneVariantsRequest(BaseModel):
    """Request model for gene variants search."""

    gene_name: str = Field(
        min_length=1,
        max_length=20,
        description="Gene symbol (e.g., CFH, BRCA1)",
    )
    limit: Optional[int] = Field(
        default=None,
        ge=1,
        le=1000,
        description="Maximum number of variants to return",
    )
    sort_by: Optional[Literal["pmids_count", "name", "rsid"]] = Field(
        default="pmids_count",
        description="Sort results by field",
    )
    sort_order: Optional[Literal["asc", "desc"]] = Field(
        default="desc",
        description="Sort order",
    )

    @field_validator("gene_name")
    @classmethod
    def validate_gene_name(cls, v: str) -> str:
        """Validate and normalize gene name."""
        v = v.strip().upper()

        if not v:
            raise ValueError("Gene name cannot be empty")

        # Basic gene symbol validation
        if not v.replace("-", "").replace("_", "").isalnum():
            raise ValueError("Gene name contains invalid characters")

        # Common gene symbol patterns
        if len(v) > 20:
            raise ValueError("Gene name is too long")

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
    format: Optional[Literal["json", "csv", "tsv"]] = Field(
        default="json",
        description="Response format",
    )

    @field_validator("variant_ids")
    @classmethod
    def validate_variant_ids(cls, v: list[str]) -> list[str]:
        """Validate list of variant IDs."""
        if not v:
            raise ValueError("At least one variant ID is required")

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
            raise ValueError("No valid variant IDs provided")

        if len(unique_ids) > 100:
            raise ValueError("Maximum 100 variant IDs allowed per request")

        return unique_ids


class CacheRequest(BaseModel):
    """Request model for cache operations."""

    operation: Literal["clear", "stats", "warm"] = Field(
        description="Cache operation to perform",
    )
    keys: Optional[list[str]] = Field(
        default=None,
        description="Specific cache keys to operate on (for selective operations)",
    )

    @field_validator("keys")
    @classmethod
    def validate_keys(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        """Validate cache keys."""
        if v is None:
            return v

        # Remove empty keys
        valid_keys = [key.strip() for key in v if key.strip()]
        return valid_keys if valid_keys else None
