"""Variant-related API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Path, Query

from litvar_link.models import (
    VariantSearchRequest,
    VariantSearchResponse,
)

from .dependencies import LoggerDep, ServiceDep
from .openapi_examples import (
    SEARCH_LIMIT_EXAMPLES,
    SEARCH_QUERY_EXAMPLES,
    SEARCH_RESPONSES,
    VARIANT_DETAILS_ID_EXAMPLES,
    VARIANT_DETAILS_RESPONSES,
)

router = APIRouter(prefix="/api/variants", tags=["Variants"])


@router.get(
    "/search",
    response_model=VariantSearchResponse,
    summary="Search genetic variants",
    description="Search for genetic variants using gene symbols, variant names, RSIDs, or HGVS notation.",
    operation_id="search_genetic_variants",
    responses=SEARCH_RESPONSES,
)
async def search_variants(
    query: str = Query(
        ...,
        min_length=1,
        max_length=100,
        description="Search query for genetic variants using various formats",
        openapi_examples=SEARCH_QUERY_EXAMPLES,
    ),
    limit: int = Query(
        10,
        ge=1,
        le=100,
        description="Maximum number of variant results to return",
        openapi_examples=SEARCH_LIMIT_EXAMPLES,
    ),
    *,
    service: ServiceDep,
    logger: LoggerDep,
) -> VariantSearchResponse:
    """Search for genetic variants using multiple query formats.

    Accepts gene symbols ("CFH"), protein/DNA changes ("p.Y402H"), RSIDs
    ("rs1061170"), and HGVS notation ("NM_000014.6:c.1204T>C"). See the
    ``query``/``limit`` OpenAPI examples for the full set. Results are LRU-cached
    and respect the LitVar2 rate limit (2 req/s). Errors map to 400 (validation),
    502 (upstream), or 500 via the app-level exception handlers.

    Args:
        query: Search query in any supported format (1-100 characters).
        limit: Maximum results to return (1-100, default 10).
        service: Injected variant service for database operations.
        logger: Structured logging service for request tracking.

    Returns:
        VariantSearchResponse with matching variants and metadata.
    """
    request = VariantSearchRequest(query=query, limit=limit)

    # PII-safe (M3): never log the query value (it can be an rsid/HGVS/gene);
    # only non-identifying request metadata is recorded.
    logger.info(
        "Variant search requested",
        limit=request.limit,
    )

    response = await service.search_variants(
        query=request.query,
        limit=request.limit,
    )

    logger.info(
        "Variant search completed",
        results_count=response.total_count,
        cached=response.cached,
    )

    return response


@router.get(
    "/details/{variant_id}",
    summary="Get detailed variant information",
    description="Retrieve comprehensive information about a specific genetic variant by ID.",
    operation_id="get_variant_details",
    responses=VARIANT_DETAILS_RESPONSES,
)
async def get_variant_details(
    variant_id: str = Path(
        ...,
        description="Variant identifier in any supported format",
        openapi_examples=VARIANT_DETAILS_ID_EXAMPLES,
    ),
    *,
    service: ServiceDep,
    logger: LoggerDep,
) -> dict[str, Any]:
    """Retrieve comprehensive information about a specific genetic variant.

    Performs a targeted single-result search for the identifier (RSID, gene +
    protein change, HGVS, or protein change) and returns a structured payload
    with a ``found`` flag, the variant details when present, caching status, and
    search timing. Errors map to 400/502/500 via the app-level handlers.

    Args:
        variant_id: Variant identifier in any supported format.
        service: Injected variant service for database operations.
        logger: Structured logging service for request tracking.

    Returns:
        Dictionary with variant details, availability status, and metadata.
    """
    # PII-safe (M3): the variant_id is an identifier and is never logged.
    logger.info("Variant details requested")

    # Search for the specific variant using search_variants
    search_response = await service.search_variants(query=variant_id, limit=1)

    # Build response based on whether variant was found
    if search_response.variants:
        variant = search_response.variants[0]
        response = {
            "variant_id": variant_id,
            "found": True,
            "variant": variant.model_dump(),
            "cached": search_response.cached,
            "search_time_ms": search_response.search_time_ms,
        }
    else:
        response = {
            "variant_id": variant_id,
            "found": False,
            "variant": None,
            "cached": search_response.cached,
            "search_time_ms": search_response.search_time_ms,
        }

    logger.info(
        "Variant details completed",
        found=response["found"],
        cached=response["cached"],
    )

    return response
