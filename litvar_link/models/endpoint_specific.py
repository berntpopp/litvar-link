"""Endpoint-specific models that match actual LitVar2 API response formats."""

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
    rsid: str | None = Field(default=None, description="Reference SNP ID if available")
    clingen_id: str | None = Field(
        default=None,
        description="ClinGen identifier if available",
    )
    data_clinical_significance: list[str] | None = Field(
        default=None,
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
        default=False,
        description="True if this is a gene-level variant",
    )
    flag_clingen_variant: bool = Field(
        default=False,
        description="True if this variant is in ClinGen database",
    )
    flag_rsid_variant: bool = Field(
        default=False,
        description="True if this variant has an RSID",
    )

    # Optional fields that sometimes appear
    rsid: str | None = Field(default=None, description="Reference SNP ID if available")
    match: str | None = Field(
        default=None,
        description="Search match description with HTML highlighting",
    )
    data_clinical_significance: list[str] | None = Field(
        default=None,
        description="Clinical significance categories",
    )


class VariantDetailsItem(BaseModel):
    """Model for variant details endpoint response.

    Every field except ``id`` carries a default. That is deliberate: this model
    is the *only* thing standing between an upstream schema change and a dead
    tool. It previously required all 16 fields, so the day LitVar2 omitted any
    one of them ``get_variant_summary`` would have raised a pydantic
    ``ValidationError`` -- which the MCP error boundary classifies ``internal``,
    i.e. an opaque "retry later" for a request that can never succeed. Absent
    upstream data must read as ABSENT (``None``/``[]``), never as a crash, and
    never as a *negative finding* (see ``data_clinical_significance``: ``None``
    means "LitVar2 said nothing", which is NOT the same as "no clinical
    significance").
    """

    model_config = {"populate_by_name": True}

    id: str = Field(alias="_id", description="Unique variant identifier")
    concept: str | None = Field(default=None, description="Type of entity (usually 'variant')")
    rsid: str | None = Field(default=None, description="Reference SNP ID")
    clingen_ids: list[str] = Field(
        default_factory=list,
        description="Associated ClinGen identifiers",
    )
    gene: list[str] = Field(default_factory=list, description="Associated gene symbols")
    name: str | None = Field(default=None, description="Variant name")
    hgvs: str | None = Field(default=None, description="HGVS notation")
    flag_gene_variant: bool = Field(
        default=False,
        description="True if this is a gene-level variant",
    )
    flag_clingen_variant: bool = Field(
        default=False,
        description="True if this variant is in ClinGen database",
    )
    flag_rsid_variant: bool = Field(default=False, description="True if this variant has an RSID")
    data_species: list[str] = Field(default_factory=list, description="Species information")
    data_snp_id: list[str] = Field(default_factory=list, description="SNP database identifiers")
    data_tax_id: list[str] = Field(default_factory=list, description="Taxonomy identifiers")
    data_allele: list[str] = Field(default_factory=list, description="Allele information")
    data_snp_class: list[str] = Field(default_factory=list, description="SNP classification")
    data_chromosome_base_position: list[str] = Field(
        default_factory=list,
        description="Chromosomal positions",
    )
    data_clinical_significance: list[str] | None = Field(
        default=None,
        description="Clinical significance categories, or None when LitVar2 supplies none",
    )
    # Upstream does not normally populate ``match`` on this endpoint, but the row
    # shape allows it. Modelled (not dropped) so an unexpected value still flows
    # through the v1.1 untrusted-text fence rather than vanishing.
    match: str | None = Field(
        default=None,
        description="Search match description with HTML highlighting",
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
