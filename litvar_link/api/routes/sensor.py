"""RSID sensor API routes."""

from __future__ import annotations

from fastapi import APIRouter, Path

from litvar_link.models import SensorResponse

from .dependencies import LoggerDep, ServiceDep
from .openapi_examples import SENSOR_RESPONSES

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
        openapi_examples={
            "cfh_y402h": {
                "summary": "CFH Y402H variant",
                "description": "Check availability of major age-related macular degeneration risk variant",
                "value": "rs1061170",
            },
            "braf_v600e": {
                "summary": "BRAF V600E oncogene",
                "description": "Check availability of common melanoma-associated mutation",
                "value": "rs113488022",
            },
            "rare_variant": {
                "summary": "Rare genetic variant",
                "description": "Check availability of less common variant (LitVar2 example)",
                "value": "rs878853264",
            },
            "brca1_founder": {
                "summary": "BRCA1 founder mutation",
                "description": "Check availability of Ashkenazi Jewish BRCA1 founder mutation",
                "value": "rs80357906",
            },
            "high_rsid": {
                "summary": "High-numbered RSID",
                "description": "Check availability of recently assigned variant identifier",
                "value": "rs1234567890",
            },
        },
    ),
    *,
    service: ServiceDep,
    logger: LoggerDep,
) -> SensorResponse:
    """Check Reference SNP ID (RSID) availability in LitVar2 database.

    This endpoint provides rapid availability checking for dbSNP Reference SNP IDs,
    essential for variant validation workflows and database integration processes.
    Returns availability status and basic variant metadata when found.

    **RSID Format Requirements:**
    - Must start with "rs" prefix (case-sensitive)
    - Followed by one or more digits (no spaces or special characters)
    - Examples: "rs1061170", "rs113488022", "rs878853264"
    - Invalid: "RS1061170", "rs_1061170", "1061170"

    **Response Information:**

    1. **Availability Status**: Boolean indicating presence in LitVar2 database
    2. **Basic Variant Info** (when available):
       - Associated gene symbol
       - HGVS protein notation for amino acid changes
       - Clinical significance classification
       - Database cross-references

    **Clinical and Research Applications:**

    - **Variant Validation**: Pre-flight checks before detailed variant queries
    - **Batch Processing**: High-throughput RSID validation in analysis pipelines
    - **Database Integration**: Cross-referencing variants between genomic databases
    - **Quality Control**: Verification of RSID lists in research datasets
    - **Clinical Workflows**: Rapid variant lookup in diagnostic laboratories
    - **Literature Mining**: Checking variant coverage before literature searches

    **Performance Characteristics:**
    - Optimized for high-frequency availability checks
    - Cached responses for frequently queried RSIDs
    - Respects LitVar2 API rate limits (2 requests/second)
    - Typical response time: 50-200ms for cached results

    **Integration Patterns:**
    - **Genomic Pipelines**: Validate RSID lists before variant annotation
    - **Clinical Systems**: Check variant availability before detailed lookups
    - **Research Tools**: Filter valid RSIDs for downstream analysis
    - **Database Synchronization**: Compare RSID coverage across platforms

    **Example Use Cases:**
    - Validate RSIDs from GWAS studies before literature review
    - Check clinical variant panel coverage in LitVar2
    - Filter valid variants for pharmacogenomics analysis
    - Verify rare variant availability for case studies

    Args:
        rsid: Reference SNP ID in format "rs" + digits (e.g., "rs1061170")
        service: Injected variant service for database operations
        logger: Structured logging service for request tracking

    Returns:
        SensorResponse with availability status and variant metadata

    Raises:
        HTTPException(400): Invalid RSID format or malformed identifier
        HTTPException(502): LitVar2 API communication or rate limit errors
        HTTPException(500): Internal server error or unexpected failures
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
