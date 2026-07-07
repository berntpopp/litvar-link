"""Publication-related API routes."""

from __future__ import annotations

from fastapi import APIRouter, Path

from litvar_link.models import PublicationResponse

from .dependencies import LoggerDep, ServiceDep
from .openapi_examples import PUBLICATIONS_ID_EXAMPLES, PUBLICATIONS_RESPONSES

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
        openapi_examples=PUBLICATIONS_ID_EXAMPLES,
    ),
    *,
    service: ServiceDep,
    logger: LoggerDep,
) -> PublicationResponse:
    """Retrieve the publication catalog associated with a genetic variant.

    Accepts RSIDs, gene + protein change, protein changes, or HGVS notation
    (see the ``variant_id`` OpenAPI examples). Returns PMIDs/PMCIDs with
    bibliographic metadata and a journal distribution for evidence review.
    Results are cached and respect the LitVar2 rate limit (2 req/s); errors map
    to 400/404/502/500 via the app-level handlers.

    Args:
        variant_id: Genetic variant identifier in any supported format.
        service: Injected variant service for database operations.
        logger: Structured logging service for request tracking.

    Returns:
        PublicationResponse with the literature catalog and metadata.
    """
    # PII-safe (M3): the variant_id is an identifier and is never logged.
    logger.info("Variant publications requested")

    response = await service.get_variant_literature(variant_id)

    logger.info(
        "Variant publications completed",
        publication_count=response.total_count,
        cached=response.cached,
    )

    return response
