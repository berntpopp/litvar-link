"""RSID sensor API routes."""

from __future__ import annotations

from fastapi import APIRouter, Path

from litvar_link.models import SensorResponse

from .dependencies import LoggerDep, ServiceDep
from .openapi_examples import SENSOR_RESPONSES, SENSOR_RSID_EXAMPLES

router = APIRouter(prefix="/api/sensor", tags=["Sensor"])


@router.get(
    "/{rsid}",
    response_model=SensorResponse,
    summary="Check RSID availability",
    description="Check if a Reference SNP ID (RSID) exists in the LitVar2 database.",
    operation_id="check_rsid_availability",
    responses=SENSOR_RESPONSES,
)
async def lookup_rsid(
    rsid: str = Path(
        ...,
        description="Reference SNP ID from dbSNP database",
        pattern=r"^rs\d+$",
        openapi_examples=SENSOR_RSID_EXAMPLES,
    ),
    *,
    service: ServiceDep,
    logger: LoggerDep,
) -> SensorResponse:
    """Check Reference SNP ID (RSID) availability in the LitVar2 database.

    Validates the ``rs`` + digits format (enforced by the path pattern) and
    returns an availability flag plus basic variant metadata when found (see the
    ``rsid`` OpenAPI examples). Useful for pre-flight validation in batch
    pipelines. Responses are cached and respect the LitVar2 rate limit (2 req/s);
    errors map to 400/502/500 via the app-level handlers.

    Args:
        rsid: Reference SNP ID in format "rs" + digits (e.g., "rs1061170").
        service: Injected variant service for database operations.
        logger: Structured logging service for request tracking.

    Returns:
        SensorResponse with availability status and variant metadata.
    """
    logger.info("RSID sensor lookup requested", rsid=rsid)

    response = await service.lookup_rsid(rsid)

    logger.info(
        "RSID sensor lookup completed",
        rsid=rsid,
        available=response.available,
        cached=response.cached,
    )

    return response
