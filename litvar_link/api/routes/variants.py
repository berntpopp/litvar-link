"""Variant-related API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from litvar_link.exceptions import LitVarAPIError, ValidationError
from litvar_link.models import (
    VariantSearchRequest,
    VariantSearchResponse,
)

from .dependencies import LoggerDep, ServiceDep

router = APIRouter(prefix="/api/variants", tags=["Variants"])


@router.get("/search", response_model=VariantSearchResponse)
async def search_variants(
    query: str = Query(..., min_length=1, max_length=100, description="Search query"),
    limit: int = Query(10, ge=1, le=100, description="Maximum results to return"),
    service: ServiceDep = None,
    logger: LoggerDep = None,
) -> VariantSearchResponse:
    """Search for genetic variants.

    This endpoint allows searching for genetic variants using various query types:
    - Gene symbols (e.g., "CFH", "BRCA1")
    - Variant names (e.g., "p.Y402H", "c.123G>A")
    - Reference SNP IDs (e.g., "rs1061170")
    - Protein changes or HGVS notation

    The search returns variants with metadata including clinical significance,
    associated genes, publication counts, and database flags.
    """
    try:
        request = VariantSearchRequest(query=query, limit=limit)

        logger.info(
            "Variant search requested",
            query=request.query,
            limit=request.limit,
        )

        response = await service.search_variants(
            query=request.query,
            limit=request.limit,
        )

        logger.info(
            "Variant search completed",
            query=request.query,
            results_count=response.total_count,
            cached=response.cached,
        )

        return response

    except ValidationError as e:
        logger.warning("Validation error in variant search", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except LitVarAPIError as e:
        logger.exception("API error in variant search", error=str(e))
        raise HTTPException(status_code=502, detail="LitVar2 API error")
    except Exception as e:
        logger.error("Unexpected error in variant search", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/details/{variant_id}")
async def get_variant_details(
    variant_id: str,
    service: ServiceDep = None,
    logger: LoggerDep = None,
) -> dict[str, Any]:
    """Get detailed information about a specific variant.

    Returns comprehensive information about a genetic variant by searching
    for the variant ID and returning the result in a structured format.
    """
    try:
        logger.info("Variant details requested", variant_id=variant_id)

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
            variant_id=variant_id,
            found=response["found"],
            cached=response["cached"],
        )

        return response

    except ValidationError as e:
        logger.warning("Validation error in variant details", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except LitVarAPIError as e:
        logger.exception("API error in variant details", error=str(e))
        raise HTTPException(status_code=502, detail="LitVar2 API error")
    except Exception as e:
        logger.error("Unexpected error in variant details", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
