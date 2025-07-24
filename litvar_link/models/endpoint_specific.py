"""Endpoint-specific models that match actual LitVar2 API response formats."""

from typing import Optional

from pydantic import BaseModel, Field


class GeneVariantItem(BaseModel):
    """Model for individual items from gene variants endpoint.

    Gene variants endpoint returns only these 2-4 fields.
    Some variants have RSIDs, others have protein notations.
    """

    model_config = {"populate_by_name": True}

    id: str = Field(alias="_id", description="Unique variant identifier")
    pmids_count: int = Field(description="Number of associated publications")

    # Optional fields that sometimes appear
    rsid: Optional[str] = Field(None, description="Reference SNP ID if available")
    clingen_id: Optional[str] = Field(
        None,
        description="ClinGen identifier if available",
    )
    data_clinical_significance: Optional[list[str]] = Field(
        None,
        description="Clinical significance annotations if available",
    )


class AutocompleteVariantItem(BaseModel):
    """Model for individual items from variant autocomplete endpoint."""

    model_config = {"populate_by_name": True}

    id: str = Field(alias="_id", description="Unique variant identifier")
    gene: list[str] = Field(description="Associated gene symbols")
    name: str = Field(description="Variant name (e.g., p.V600E)")
    hgvs: str = Field(default="", description="HGVS notation")
    pmids_count: int = Field(description="Number of associated publications")
    flag_gene_variant: bool = Field(
        default=False, description="True if this is a gene-level variant",
    )
    flag_clingen_variant: bool = Field(
        default=False,
        description="True if this variant is in ClinGen database",
    )
    flag_rsid_variant: bool = Field(
        default=False, description="True if this variant has an RSID",
    )

    # Optional fields that sometimes appear
    rsid: Optional[str] = Field(None, description="Reference SNP ID if available")
    match: Optional[str] = Field(
        None,
        description="Search match description with HTML highlighting",
    )
    data_clinical_significance: Optional[list[str]] = Field(
        None,
        description="Clinical significance categories",
    )


class VariantDetailsItem(BaseModel):
    """Model for variant details endpoint response."""

    model_config = {"populate_by_name": True}

    id: str = Field(alias="_id", description="Unique variant identifier")
    concept: str = Field(description="Type of entity (usually 'variant')")
    rsid: str = Field(description="Reference SNP ID")
    clingen_ids: list[str] = Field(description="Associated ClinGen identifiers")
    gene: list[str] = Field(description="Associated gene symbols")
    name: str = Field(description="Variant name")
    hgvs: str = Field(description="HGVS notation")
    flag_gene_variant: bool = Field(description="True if this is a gene-level variant")
    flag_clingen_variant: bool = Field(
        description="True if this variant is in ClinGen database",
    )
    flag_rsid_variant: bool = Field(description="True if this variant has an RSID")
    data_species: list[str] = Field(description="Species information")
    data_snp_id: list[str] = Field(description="SNP database identifiers")
    data_tax_id: list[str] = Field(description="Taxonomy identifiers")
    data_allele: list[str] = Field(description="Allele information")
    data_snp_class: list[str] = Field(description="SNP classification")
    data_chromosome_base_position: list[str] = Field(
        description="Chromosomal positions",
    )
    data_clinical_significance: list[str] = Field(
        description="Clinical significance categories",
    )


class SensorItem(BaseModel):
    """Model for RSID sensor endpoint response."""

    pmids_count: int = Field(description="Number of associated publications")
    rsid: str = Field(description="Reference SNP ID")
    link: str = Field(description="Direct URL to LitVar2 page")
    logo: str = Field(description="LitVar2 logo URL")


class PublicationsItem(BaseModel):
    """Model for variant publications endpoint response."""

    pmids: list[int] = Field(description="List of PubMed IDs")
