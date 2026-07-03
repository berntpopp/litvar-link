"""Core variant data models for LitVar-Link."""

from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class ClinicalSignificance(StrEnum):
    """Clinical significance categories for variants."""

    BENIGN = "benign"
    LIKELY_BENIGN = "likely benign"
    UNCERTAIN_SIGNIFICANCE = "uncertain significance"
    LIKELY_PATHOGENIC = "likely pathogenic"
    PATHOGENIC = "pathogenic"
    RISK_FACTOR = "risk factor"
    AFFECTS = "affects"
    ASSOCIATION = "association"
    DRUG_RESPONSE = "drug response"
    PROTECTIVE = "protective"
    CONFLICTING = "conflicting interpretations"
    OTHER = "other"


class Publication(BaseModel):
    """Publication reference model."""

    pmid: str = Field(description="PubMed ID")
    pmcid: str | None = Field(default=None, description="PMC ID if available")
    title: str | None = Field(default=None, description="Publication title")
    authors: list[str] | None = Field(default=None, description="List of authors")
    journal: str | None = Field(default=None, description="Journal name")
    pub_date: str | None = Field(default=None, description="Publication date")
    doi: str | None = Field(default=None, description="DOI")

    @field_validator("pmid")
    @classmethod
    def validate_pmid(cls, v: str) -> str:
        """Validate PMID format."""
        if not v.isdigit():
            msg = "PMID must contain only digits"
            raise ValueError(msg)
        if len(v) < 1 or len(v) > 8:
            msg = "PMID must be 1-8 digits long"
            raise ValueError(msg)
        return v

    @field_validator("pmcid")
    @classmethod
    def validate_pmcid(cls, v: str | None) -> str | None:
        """Validate PMCID format."""
        if v is None:
            return v
        if not v.startswith("PMC"):
            msg = "PMCID must start with 'PMC'"
            raise ValueError(msg)
        if not v[3:].isdigit():
            msg = "PMCID must have digits after 'PMC'"
            raise ValueError(msg)
        return v


class Variant(BaseModel):
    """Core variant model based on LitVar2 API responses."""

    id: str = Field(alias="_id", description="Unique variant identifier")
    rsid: str | None = Field(default=None, description="Reference SNP ID (e.g., rs1061170)")
    gene: list[str] | None = Field(default=None, description="Associated gene symbols")
    name: str | None = Field(default=None, description="Variant name (e.g., p.Y402H)")
    hgvs: str | None = Field(default=None, description="HGVS notation")
    pmids_count: int | None = Field(
        default=None,
        description="Number of associated publications",
    )

    # Clinical annotations
    clinical_significance: list[str] | None = Field(
        default=None,
        alias="data_clinical_significance",
        description="Clinical significance categories",
    )

    # Variant classification flags
    flag_gene_variant: bool | None = Field(
        default=None,
        description="True if this is a gene-level variant",
    )
    flag_clingen_variant: bool | None = Field(
        default=None,
        description="True if this variant is in ClinGen database",
    )
    flag_rsid_variant: bool | None = Field(
        default=None,
        description="True if this variant has an RSID",
    )

    # Search-specific fields
    match: str | None = Field(
        default=None,
        description="Search match description with HTML highlighting",
    )

    # ClinGen specific
    clingen_id: str | None = Field(default=None, description="ClinGen identifier")

    @field_validator("rsid")
    @classmethod
    def validate_rsid(cls, v: str | None) -> str | None:
        """Validate RSID format."""
        if v is None:
            return v
        if not v.startswith("rs"):
            msg = "RSID must start with 'rs'"
            raise ValueError(msg)
        if not v[2:].isdigit():
            msg = "RSID must have digits after 'rs'"
            raise ValueError(msg)
        return v

    @field_validator("gene")
    @classmethod
    def validate_gene_list(cls, v: list[str] | None) -> list[str] | None:
        """Validate gene symbol list."""
        if v is None or not v:
            return None

        # Remove empty strings and duplicates while preserving order
        cleaned = []
        seen = set()
        for gene in v:
            if gene and gene not in seen:
                cleaned.append(gene.upper())  # Normalize to uppercase
                seen.add(gene.upper())

        return cleaned if cleaned else None

    @field_validator("pmids_count")
    @classmethod
    def validate_pmids_count(cls, v: int | None) -> int | None:
        """Validate publication count is non-negative."""
        if v is not None and v < 0:
            msg = "Publication count cannot be negative"
            raise ValueError(msg)
        return v

    @field_validator("clinical_significance")
    @classmethod
    def validate_clinical_significance(
        cls,
        v: list[str] | None,
    ) -> list[str] | None:
        """Validate clinical significance values."""
        if v is None or not v:
            return None

        # Normalize values and filter valid ones
        valid_values = {sig.value for sig in ClinicalSignificance}
        normalized = []

        for sig in v:
            if isinstance(sig, str):
                sig_lower = sig.lower().strip()
                if sig_lower in valid_values or sig_lower:
                    normalized.append(sig_lower)

        return normalized if normalized else None

    @property
    def display_name(self) -> str:
        """Get display name for the variant."""
        if self.name:
            return self.name
        if self.rsid:
            return self.rsid
        if self.gene:
            return f"{'/'.join(self.gene)} variant"
        return self.id

    @property
    def is_pathogenic(self) -> bool:
        """Check if variant has pathogenic clinical significance."""
        if not self.clinical_significance:
            return False

        pathogenic_terms = {
            ClinicalSignificance.PATHOGENIC.value,
            ClinicalSignificance.LIKELY_PATHOGENIC.value,
        }

        return any(sig in pathogenic_terms for sig in self.clinical_significance)

    @property
    def is_benign(self) -> bool:
        """Check if variant has benign clinical significance."""
        if not self.clinical_significance:
            return False

        benign_terms = {
            ClinicalSignificance.BENIGN.value,
            ClinicalSignificance.LIKELY_BENIGN.value,
        }

        return any(sig in benign_terms for sig in self.clinical_significance)


class VariantDetails(Variant):
    """Extended variant model with additional details."""

    # Genomic coordinates
    chromosome: str | None = Field(default=None, description="Chromosome")
    position: int | None = Field(default=None, description="Genomic position")
    ref_allele: str | None = Field(default=None, description="Reference allele")
    alt_allele: str | None = Field(default=None, description="Alternative allele")

    # Additional annotations
    consequence: str | None = Field(default=None, description="Variant consequence")
    protein_change: str | None = Field(default=None, description="Protein-level change")
    transcript_id: str | None = Field(default=None, description="Transcript identifier")

    # Database cross-references
    dbsnp_id: str | None = Field(default=None, description="dbSNP identifier")
    clinvar_id: str | None = Field(default=None, description="ClinVar identifier")
    cosmic_id: str | None = Field(default=None, description="COSMIC identifier")

    # Frequency data
    allele_frequency: float | None = Field(
        default=None,
        description="Population allele frequency",
    )
    minor_allele_frequency: float | None = Field(
        default=None,
        description="Minor allele frequency",
    )

    # Associated publications
    publications: list[Publication] | None = Field(
        default=None,
        description="List of associated publications",
    )

    @field_validator("position")
    @classmethod
    def validate_position(cls, v: int | None) -> int | None:
        """Validate genomic position is positive."""
        if v is not None and v <= 0:
            msg = "Genomic position must be positive"
            raise ValueError(msg)
        return v

    @field_validator("allele_frequency", "minor_allele_frequency")
    @classmethod
    def validate_frequency(cls, v: float | None) -> float | None:
        """Validate allele frequency is between 0 and 1."""
        if v is not None and (v < 0.0 or v > 1.0):
            msg = "Allele frequency must be between 0.0 and 1.0"
            raise ValueError(msg)
        return v

    @field_validator("chromosome")
    @classmethod
    def validate_chromosome(cls, v: str | None) -> str | None:
        """Validate chromosome format."""
        if v is None:
            return v

        # Normalize chromosome format
        v = v.upper().strip()

        # Valid chromosomes: 1-22, X, Y, MT
        valid_chroms = {str(i) for i in range(1, 23)} | {"X", "Y", "MT", "M"}

        # Handle different prefixes
        chrom = v.removeprefix("CHR")

        if chrom in valid_chroms:
            return chrom

        # Return as-is for non-standard chromosomes (contigs, etc.)
        return v
