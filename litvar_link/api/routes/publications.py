"""Publication-related API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Path

from litvar_link.exceptions import LitVarAPIError, ValidationError
from litvar_link.models import PublicationResponse
from .dependencies import LoggerDep, ServiceDep

router = APIRouter(prefix="/api/publications", tags=["Publications"])


@router.get(
    "/variant/{variant_id}",
    response_model=PublicationResponse,
    summary="Get variant-associated publications",
    description="Retrieve all publications that mention or study a specific genetic variant.",
    operation_id="get_variant_publications",
    responses={
        200: {
            "description": "Publications retrieved successfully with metadata",
            "content": {
                "application/json": {
                    "example": {
                        "variant_id": "rs1061170",
                        "total_count": 127,
                        "publications": [
                            {
                                "pmid": "32511357",
                                "pmcid": "PMC7279073",
                                "title": "Complement factor H Y402H polymorphism and age-related macular degeneration",
                                "journal": "Nature Genetics",
                                "publication_year": 2020,
                                "study_type": "genome-wide association study",
                            },
                            {
                                "pmid": "29355051",
                                "title": "CFH variants and AMD risk in European populations",
                                "journal": "Human Genetics",
                                "publication_year": 2018,
                                "study_type": "meta-analysis",
                            },
                        ],
                        "journal_distribution": {
                            "Nature Genetics": 23,
                            "Human Genetics": 18,
                            "PLOS Genetics": 15,
                        },
                        "cached": False,
                        "search_time_ms": 341,
                    },
                },
            },
        },
        404: {
            "description": "No publications found for variant",
            "content": {
                "application/json": {
                    "example": {
                        "variant_id": "rs999999999",
                        "total_count": 0,
                        "publications": [],
                        "message": "No publications found for variant rs999999999",
                    },
                },
            },
        },
        400: {
            "description": "Invalid variant identifier format",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Invalid variant ID format. Expected RSID, gene symbol, or HGVS notation",
                    },
                },
            },
        },
        502: {
            "description": "LitVar2 API communication error",
            "content": {
                "application/json": {"example": {"detail": "LitVar2 API error"}},
            },
        },
    },
)
async def get_variant_publications(
    variant_id: str = Path(
        ...,
        description="Genetic variant identifier for literature search",
        openapi_examples={
            "cfh_amd_variant": {
                "summary": "CFH Y402H AMD variant",
                "description": "Get publications for major age-related macular degeneration risk variant",
                "value": "rs1061170",
            },
            "braf_melanoma": {
                "summary": "BRAF V600E melanoma",
                "description": "Get publications for common BRAF mutation in melanoma research",
                "value": "rs113488022",
            },
            "brca1_founder": {
                "summary": "BRCA1 founder mutation",
                "description": "Get publications for Ashkenazi Jewish BRCA1 founder mutation",
                "value": "rs80357906",
            },
            "protein_notation": {
                "summary": "Protein change notation",
                "description": "Get publications using amino acid change description",
                "value": "p.V600E",
            },
            "gene_variant": {
                "summary": "Gene-specific variant",
                "description": "Get publications for gene symbol with protein change",
                "value": "CFH p.Y402H",
            },
        },
    ),
    service: ServiceDep = ...,
    logger: LoggerDep = ...,
) -> PublicationResponse:
    """Retrieve comprehensive literature for genetic variant research.

    This endpoint provides complete publication cataloging for genetic variants,
    essential for evidence-based variant interpretation, literature reviews,
    and clinical decision-making in genomic medicine.

    **Supported Variant Identifiers:**
    - **RSIDs**: Reference SNP IDs from dbSNP (e.g., "rs1061170")
    - **Gene Variants**: Gene symbol with protein change (e.g., "CFH p.Y402H")
    - **Protein Changes**: Amino acid substitutions (e.g., "p.V600E")
    - **HGVS Notation**: Standard nomenclature (e.g., "NM_000059.4:c.68A>G")

    **Publication Data Provided:**

    1. **Core Identifiers:**
       - PubMed IDs (PMIDs) for direct PubMed access
       - PubMed Central IDs (PMCIDs) for full-text articles
       - Digital Object Identifiers (DOIs) when available

    2. **Bibliographic Metadata:**
       - Article titles and abstracts
       - Journal names and impact factors
       - Publication years and citation counts
       - Author information and affiliations

    3. **Research Context:**
       - Study types (GWAS, case-control, meta-analysis)
       - Population demographics and sample sizes
       - Clinical significance assessments
       - Functional impact analyses

    **Clinical and Research Applications:**

    - **Variant Interpretation**: Evidence collection for clinical variant classification
    - **Literature Reviews**: Systematic review preparation for specific variants
    - **Clinical Guidelines**: Supporting evidence for diagnostic and therapeutic decisions
    - **Research Planning**: Gap analysis and research prioritization
    - **Meta-Analyses**: Data source identification for systematic reviews
    - **Clinical Trials**: Background literature for variant-based therapeutic studies

    **Evidence Quality Assessment:**
    Publications are ranked by relevance, study quality, and citation impact
    to support evidence-based clinical decision-making and research prioritization.

    **Integration Workflows:**
    - **Clinical Labs**: Literature evidence for variant interpretation reports
    - **Genetic Counseling**: Supporting materials for patient consultations
    - **Research Databases**: Literature curation for variant knowledge bases
    - **Pharmaceutical R&D**: Target validation and drug development support

    **Performance Features:**
    - Results cached for frequently queried variants
    - Respects LitVar2 API rate limits (2 requests/second)
    - Optimized for high-impact variants with extensive literature

    Args:
        variant_id: Genetic variant identifier in any supported format
        service: Injected variant service for database operations
        logger: Structured logging service for request tracking

    Returns:
        PublicationResponse with complete literature catalog and metadata

    Raises:
        HTTPException(400): Invalid variant identifier format or unsupported notation
        HTTPException(404): Variant not found or no associated publications
        HTTPException(502): LitVar2 API communication or rate limit errors
        HTTPException(500): Internal server error or unexpected failures
    """
    try:
        logger.info("Variant publications requested", variant_id=variant_id)

        response = await service.get_variant_literature(variant_id)

        logger.info(
            "Variant publications completed",
            variant_id=variant_id,
            publication_count=response.total_count,
            cached=response.cached,
        )

        return response

    except ValidationError as e:
        logger.warning("Validation error in variant publications", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except LitVarAPIError as e:
        logger.exception("API error in variant publications", error=str(e))
        raise HTTPException(status_code=502, detail="LitVar2 API error")
    except Exception as e:
        logger.error(
            "Unexpected error in variant publications",
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Internal server error")
