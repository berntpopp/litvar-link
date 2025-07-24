"""Publication-related API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from litvar_link.exceptions import LitVarAPIError, ValidationError
from litvar_link.models import PublicationResponse

from .dependencies import LoggerDep, ServiceDep

router = APIRouter(prefix="/api/publications", tags=["Publications"])


@router.get("/variant/{variant_id}", response_model=PublicationResponse)
async def get_variant_publications(
    variant_id: str,
    service: ServiceDep = None,
    logger: LoggerDep = None,
) -> PublicationResponse:
    """Get publications associated with a genetic variant.

    Returns all publications (PMIDs and PMCIDs) that mention or study
    the specified genetic variant. This is useful for:
    - Literature review of variant studies
    - Evidence collection for variant interpretation
    - Finding research papers about specific variants
    - Building comprehensive variant knowledge bases

    The response includes publication metadata and statistics.
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
