"""Publication-related API routes."""

from __future__ import annotations

from fastapi import APIRouter, Path

from litvar_link.models import PublicationResponse

from .dependencies import LoggerDep, ServiceDep
from .openapi_examples import PUBLICATIONS_RESPONSES

router = APIRouter(prefix="/api/publications", tags=["Publications"])


@router.get(
    "/variant/{variant_id}",
    response_model=PublicationResponse,
    summary="Get variant-associated publications",
    description="Retrieve all publications that mention or study a specific genetic variant.",
    operation_id="get_variant_publications",
    responses=PUBLICATIONS_RESPONSES,
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
    *,
    service: ServiceDep,
    logger: LoggerDep,
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
    logger.info("Variant publications requested", variant_id=variant_id)

    response = await service.get_variant_literature(variant_id)

    logger.info(
        "Variant publications completed",
        variant_id=variant_id,
        publication_count=response.total_count,
        cached=response.cached,
    )

    return response
