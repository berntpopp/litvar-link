"""RSID sensor API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ...exceptions import LitVarAPIError, ValidationError
from ...models import SensorResponse
from .dependencies import LoggerDep, ServiceDep

router = APIRouter(prefix="/api/sensor", tags=["Sensor"])


@router.get("/{rsid}", response_model=SensorResponse)
async def lookup_rsid(
    rsid: str,
    service: ServiceDep = None,
    logger: LoggerDep = None,
) -> SensorResponse:
    """Check if a Reference SNP ID (RSID) is available in LitVar2.

    This endpoint provides a quick way to check if a specific RSID
    exists in the LitVar2 database and returns basic information if available.

    Useful for:
    - Validating RSIDs before detailed queries
    - Batch processing of RSID lists
    - Quick availability checks in automated workflows
    - Integration with other genomic databases

    RSIDs should be in the format "rs" followed by digits (e.g., "rs1061170").
    The response includes availability status and basic variant metadata if found.
    """
    try:
        logger.info("RSID sensor lookup requested", rsid=rsid)

        response = await service.lookup_rsid(rsid)

        logger.info(
            "RSID sensor lookup completed",
            rsid=rsid,
            available=response.available,
            cached=response.cached,
        )

        return response

    except ValidationError as e:
        logger.warning("Validation error in RSID lookup", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except LitVarAPIError as e:
        logger.error("API error in RSID lookup", error=str(e))
        raise HTTPException(status_code=502, detail="LitVar2 API error")
    except Exception as e:
        logger.error("Unexpected error in RSID lookup", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
