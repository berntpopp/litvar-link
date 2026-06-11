"""Gene-related API routes."""

from __future__ import annotations

from fastapi import APIRouter, Path

from litvar_link.models import GeneVariantsResponse

from .dependencies import LoggerDep, ServiceDep
from .openapi_examples import GENE_NAME_EXAMPLES, GENE_VARIANTS_RESPONSES

router = APIRouter(prefix="/api/genes", tags=["Genes"])


@router.get(
    "/{gene_name}/variants",
    response_model=GeneVariantsResponse,
    summary="Get gene-associated variants",
    description="Retrieve all genetic variants associated with a specific gene symbol.",
    operation_id="get_gene_variants",
    responses=GENE_VARIANTS_RESPONSES,
)
async def get_gene_variants(
    gene_name: str = Path(
        ...,
        description="Official HUGO gene symbol for variant lookup",
        openapi_examples=GENE_NAME_EXAMPLES,
    ),
    *,
    service: ServiceDep,
    logger: LoggerDep,
) -> GeneVariantsResponse:
    """Retrieve the full variant catalog for a gene with significance stats.

    Expects an official (uppercase) HUGO/HGNC symbol such as "CFH" or "BRCA1"
    (see the ``gene_name`` OpenAPI examples). Returns per-gene totals plus
    pathogenic/benign/uncertain counts and individual variant details. Results
    are LRU-cached and respect the LitVar2 rate limit (2 req/s); errors map to
    400/404/502/500 via the app-level handlers.

    Args:
        gene_name: Official HUGO gene symbol (case-sensitive uppercase).
        service: Injected variant service for database operations.
        logger: Structured logging service for request tracking.

    Returns:
        GeneVariantsResponse with the variant catalog and statistics.
    """
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
