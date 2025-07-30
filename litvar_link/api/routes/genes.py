"""Gene-related API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Path

from litvar_link.exceptions import LitVarAPIError, ValidationError
from litvar_link.models import GeneVariantsResponse
from .dependencies import LoggerDep, ServiceDep

router = APIRouter(prefix="/api/genes", tags=["Genes"])


@router.get(
    "/{gene_name}/variants",
    response_model=GeneVariantsResponse,
    summary="Get gene-associated variants",
    description="Retrieve all genetic variants associated with a specific gene symbol.",
    operation_id="get_gene_variants",
    responses={
        200: {
            "description": "Gene variants retrieved successfully with statistics",
            "content": {
                "application/json": {
                    "example": {
                        "gene_name": "CFH",
                        "total_count": 234,
                        "pathogenic_count": 45,
                        "benign_count": 123,
                        "uncertain_count": 66,
                        "variants": [
                            {
                                "id": "rs1061170",
                                "hgvs_protein": "p.Y402H",
                                "clinical_significance": "pathogenic",
                                "publication_count": 127,
                                "allele_frequency": 0.23,
                            },
                            {
                                "id": "rs9970784",
                                "hgvs_protein": "p.I62V",
                                "clinical_significance": "benign",
                                "publication_count": 34,
                                "allele_frequency": 0.45,
                            },
                        ],
                        "cached": False,
                        "search_time_ms": 567,
                    },
                },
            },
        },
        400: {
            "description": "Invalid gene symbol format",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Invalid gene symbol. Must be a valid HUGO gene symbol",
                    },
                },
            },
        },
        404: {
            "description": "Gene not found or no variants available",
            "content": {
                "application/json": {
                    "example": {
                        "gene_name": "NONEXISTENT",
                        "total_count": 0,
                        "variants": [],
                        "message": "No variants found for gene NONEXISTENT",
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
async def get_gene_variants(
    gene_name: str = Path(
        ...,
        description="Official HUGO gene symbol for variant lookup",
        openapi_examples={
            "cfh_complement": {
                "summary": "Complement factor H gene",
                "description": "Get variants in complement factor H gene (major age-related macular degeneration gene)",
                "value": "CFH",
            },
            "brca1_oncology": {
                "summary": "BRCA1 tumor suppressor",
                "description": "Comprehensive variants in BRCA1 breast cancer gene",
                "value": "BRCA1",
            },
            "brca2_oncology": {
                "summary": "BRCA2 tumor suppressor",
                "description": "Get variants in BRCA2 hereditary breast cancer gene",
                "value": "BRCA2",
            },
            "naa10_rare": {
                "summary": "NAA10 acetyltransferase",
                "description": "N-alpha-acetyltransferase variants (LitVar2 example dataset)",
                "value": "NAA10",
            },
            "braf_oncogene": {
                "summary": "BRAF proto-oncogene",
                "description": "Get variants in BRAF gene (common in melanoma and other cancers)",
                "value": "BRAF",
            },
        },
    ),
    service: ServiceDep = ...,
    logger: LoggerDep = ...,
) -> GeneVariantsResponse:
    """Retrieve comprehensive variant information for a specific gene.

    This endpoint provides complete variant cataloging for a gene, including
    detailed variant information, clinical significance statistics, and
    publication evidence counts for comprehensive gene-centric analysis.

    **Gene Symbol Requirements:**
    - Must be official HUGO Gene Nomenclature Committee (HGNC) symbols
    - Case-sensitive (use uppercase: "BRCA1", not "brca1")
    - Examples: "CFH", "BRCA1", "BRCA2", "NAA10", "BRAF"

    **Response Information:**

    1. **Variant Statistics:**
       - Total variant count for the gene
       - Pathogenic variant count (clinical significance)
       - Benign variant count (likely harmless)
       - Variants of uncertain significance (VUS) count

    2. **Individual Variant Details:**
       - Reference SNP IDs (RSIDs) for database cross-referencing
       - HGVS protein notation for amino acid changes
       - Clinical significance classifications
       - Publication counts for evidence assessment
       - Population allele frequencies when available

    **Clinical Applications:**
    - **Gene Panel Analysis**: Comprehensive variant review for clinical panels
    - **Variant Interpretation**: Evidence-based pathogenicity assessment
    - **Research Planning**: Literature gap analysis and research prioritization
    - **Population Genetics**: Frequency analysis and ethnic variation studies
    - **Diagnostic Workflows**: Clinical variant classification and reporting

    **Performance Features:**
    - Results cached using async LRU caching for rapid repeat queries
    - Respects LitVar2 API rate limits (2 requests/second)
    - Optimized for large gene variant sets (e.g., BRCA1 with 1000+ variants)

    **Use Cases by Gene Type:**
    - **Tumor Suppressors** (BRCA1, BRCA2): Cancer predisposition analysis
    - **Complement Genes** (CFH): Age-related macular degeneration research
    - **Acetyltransferases** (NAA10): Rare disease variant characterization
    - **Proto-oncogenes** (BRAF): Somatic mutation analysis in cancer

    Args:
        gene_name: Official HUGO gene symbol (case-sensitive uppercase)
        service: Injected variant service for database operations
        logger: Structured logging service for request tracking

    Returns:
        GeneVariantsResponse with complete variant catalog and statistics

    Raises:
        HTTPException(400): Invalid gene symbol format or unsupported gene
        HTTPException(404): Gene not found or no variants available in database
        HTTPException(502): LitVar2 API communication or rate limit errors
        HTTPException(500): Internal server error or unexpected failures
    """
    try:
        logger.info("Gene variants requested", gene_name=gene_name)

        response = await service.search_gene_variants(gene_name)

        logger.info(
            "Gene variants completed",
            gene_name=gene_name,
            variant_count=response.total_count,
            pathogenic_count=response.pathogenic_count,
            benign_count=response.benign_count,
            cached=response.cached,
        )

        return response

    except ValidationError as e:
        logger.warning("Validation error in gene variants", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except LitVarAPIError as e:
        logger.exception("API error in gene variants", error=str(e))
        raise HTTPException(status_code=502, detail="LitVar2 API error")
    except Exception as e:
        logger.error("Unexpected error in gene variants", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
