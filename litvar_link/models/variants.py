"""Core variant data models for LitVar-Link."""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class ClinicalSignificance(str, Enum):
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
    pmcid: Optional[str] = Field(None, description="PMC ID if available")
    title: Optional[str] = Field(None, description="Publication title")
    authors: Optional[list[str]] = Field(None, description="List of authors")
    journal: Optional[str] = Field(None, description="Journal name")
    pub_date: Optional[str] = Field(None, description="Publication date")
    doi: Optional[str] = Field(None, description="DOI")

    @field_validator("pmid")
    @classmethod
    def validate_pmid(cls, v: str) -> str:
        """Validate PMID format."""
        if not v.isdigit():
            raise ValueError("PMID must contain only digits")
        if len(v) < 7 or len(v) > 8:
            raise ValueError("PMID must be 7-8 digits long")
        return v

    @field_validator("pmcid")
    @classmethod
    def validate_pmcid(cls, v: Optional[str]) -> Optional[str]:
        """Validate PMCID format."""
        if v is None:
            return v
        if not v.startswith("PMC"):
            raise ValueError("PMCID must start with 'PMC'")
        if not v[3:].isdigit():
            raise ValueError("PMCID must have digits after 'PMC'")
        return v


class Variant(BaseModel):
    """Core variant model based on LitVar2 API responses."""

    id: str = Field(alias="_id", description="Unique variant identifier")
    rsid: Optional[str] = Field(None, description="Reference SNP ID (e.g., rs1061170)")
    gene: Optional[list[str]] = Field(None, description="Associated gene symbols")
    name: Optional[str] = Field(None, description="Variant name (e.g., p.Y402H)")
    hgvs: Optional[str] = Field(None, description="HGVS notation")
    pmids_count: Optional[int] = Field(
        None,
        description="Number of associated publications",
    )

    # Clinical annotations
    clinical_significance: Optional[list[str]] = Field(
        None,
        alias="data_clinical_significance",
        description="Clinical significance categories",
    )

    # Variant classification flags
    flag_gene_variant: Optional[bool] = Field(
        None,
        description="True if this is a gene-level variant",
    )
    flag_clingen_variant: Optional[bool] = Field(
        None,
        description="True if this variant is in ClinGen database",
    )
    flag_rsid_variant: Optional[bool] = Field(
        None,
        description="True if this variant has an RSID",
    )

    # Search-specific fields
    match: Optional[str] = Field(
        None,
        description="Search match description with HTML highlighting",
    )

    # ClinGen specific
    clingen_id: Optional[str] = Field(None, description="ClinGen identifier")

    @field_validator("rsid")
    @classmethod
    def validate_rsid(cls, v: Optional[str]) -> Optional[str]:
        """Validate RSID format."""
        if v is None:
            return v
        if not v.startswith("rs"):
            raise ValueError("RSID must start with 'rs'")
        if not v[2:].isdigit():
            raise ValueError("RSID must have digits after 'rs'")
        return v

    @field_validator("gene")
    @classmethod
    def validate_gene_list(cls, v: Optional[list[str]]) -> Optional[list[str]]:
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
    def validate_pmids_count(cls, v: Optional[int]) -> Optional[int]:
        """Validate publication count is non-negative."""
        if v is not None and v < 0:
            raise ValueError("Publication count cannot be negative")
        return v

    @field_validator("clinical_significance")
    @classmethod
    def validate_clinical_significance(
        cls,
        v: Optional[list[str]],
    ) -> Optional[list[str]]:
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
    chromosome: Optional[str] = Field(None, description="Chromosome")
    position: Optional[int] = Field(None, description="Genomic position")
    ref_allele: Optional[str] = Field(None, description="Reference allele")
    alt_allele: Optional[str] = Field(None, description="Alternative allele")

    # Additional annotations
    consequence: Optional[str] = Field(None, description="Variant consequence")
    protein_change: Optional[str] = Field(None, description="Protein-level change")
    transcript_id: Optional[str] = Field(None, description="Transcript identifier")

    # Database cross-references
    dbsnp_id: Optional[str] = Field(None, description="dbSNP identifier")
    clinvar_id: Optional[str] = Field(None, description="ClinVar identifier")
    cosmic_id: Optional[str] = Field(None, description="COSMIC identifier")

    # Frequency data
    allele_frequency: Optional[float] = Field(
        None,
        description="Population allele frequency",
    )
    minor_allele_frequency: Optional[float] = Field(
        None,
        description="Minor allele frequency",
    )

    # Associated publications
    publications: Optional[list[Publication]] = Field(
        None,
        description="List of associated publications",
    )

    @field_validator("position")
    @classmethod
    def validate_position(cls, v: Optional[int]) -> Optional[int]:
        """Validate genomic position is positive."""
        if v is not None and v <= 0:
            raise ValueError("Genomic position must be positive")
        return v

    @field_validator("allele_frequency", "minor_allele_frequency")
    @classmethod
    def validate_frequency(cls, v: Optional[float]) -> Optional[float]:
        """Validate allele frequency is between 0 and 1."""
        if v is not None and (v < 0.0 or v > 1.0):
            raise ValueError("Allele frequency must be between 0.0 and 1.0")
        return v

    @field_validator("chromosome")
    @classmethod
    def validate_chromosome(cls, v: Optional[str]) -> Optional[str]:
        """Validate chromosome format."""
        if v is None:
            return v

        # Normalize chromosome format
        v = v.upper().strip()

        # Valid chromosomes: 1-22, X, Y, MT
        valid_chroms = {str(i) for i in range(1, 23)} | {"X", "Y", "MT", "M"}

        # Handle different prefixes
        if v.startswith("CHR"):
            chrom = v[3:]
        else:
            chrom = v

        if chrom in valid_chroms:
            return chrom

        # Return as-is for non-standard chromosomes (contigs, etc.)
        return v
