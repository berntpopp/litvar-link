"""Variant-related API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Path, Query

from litvar_link.models import (
    VariantSearchRequest,
    VariantSearchResponse,
)

from .dependencies import LoggerDep, ServiceDep

router = APIRouter(prefix="/api/variants", tags=["Variants"])


@router.get(
    "/search",
    response_model=VariantSearchResponse,
    summary="Search genetic variants",
    description="Search for genetic variants using gene symbols, variant names, RSIDs, or HGVS notation.",
    operation_id="search_genetic_variants",
    responses={
        200: {
            "description": "Variant search results with metadata",
            "content": {
                "application/json": {
                    "example": {
                        "query": "CFH p.Y402H",
                        "total_count": 15,
                        "variants": [
                            {
                                "id": "rs1061170",
                                "gene": "CFH",
                                "hgvs_protein": "p.Y402H",
                                "clinical_significance": "pathogenic",
                                "publication_count": 127,
                            },
                        ],
                        "cached": False,
                        "search_time_ms": 245,
                    },
                },
            },
        },
        400: {
            "description": "Invalid query parameters or format",
            "content": {
                "application/json": {
                    "example": {"detail": "Query must be between 1 and 100 characters"},
                },
            },
        },
        422: {
            "description": "Query validation error",
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid HGVS notation format"},
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
async def search_variants(
    query: str = Query(
        ...,
        min_length=1,
        max_length=100,
        description="Search query for genetic variants using various formats",
        openapi_examples={
            "cfh_variant": {
                "summary": "CFH complement factor variant",
                "description": "Search for Y402H variant in complement factor H gene (LitVar2 example)",
                "value": "CFH p.Y402H",
            },
            "brca1_mutation": {
                "summary": "BRCA1 pathogenic mutation",
                "description": "Search for Met1Val mutation in BRCA1 tumor suppressor gene",
                "value": "BRCA1 p.Met1Val",
            },
            "rsid_lookup": {
                "summary": "Reference SNP ID lookup",
                "description": "Direct lookup using dbSNP reference ID",
                "value": "rs1061170",
            },
            "hgvs_notation": {
                "summary": "HGVS genomic notation",
                "description": "Search using Human Genome Variation Society notation",
                "value": "NM_000014.6:c.1204T>C",
            },
            "gene_symbol": {
                "summary": "Gene symbol search",
                "description": "Find all variants in specific gene",
                "value": "NAA10",
            },
            "protein_change": {
                "summary": "Protein change notation",
                "description": "Search using amino acid change description",
                "value": "p.V600E",
            },
        },
    ),
    limit: int = Query(
        10,
        ge=1,
        le=100,
        description="Maximum number of variant results to return",
        openapi_examples={
            "default_limit": {
                "summary": "Default result count",
                "description": "Return standard 10 results for quick overview",
                "value": 10,
            },
            "comprehensive_search": {
                "summary": "Comprehensive results",
                "description": "Return up to 50 results for detailed analysis",
                "value": 50,
            },
            "maximum_results": {
                "summary": "Maximum allowed results",
                "description": "Return maximum 100 results for exhaustive search",
                "value": 100,
            },
        },
    ),
    *,
    service: ServiceDep,
    logger: LoggerDep,
) -> VariantSearchResponse:
    """Search for genetic variants using multiple query formats.

    This endpoint provides comprehensive search capabilities across LitVar2's
    genetic variant database, supporting various query formats for flexible
    variant discovery and clinical analysis.

    **Supported Query Types:**

    1. **Gene Symbols**: Official HUGO gene symbols
       - Example: "CFH" (complement factor H gene variants)
       - Example: "BRCA1" (breast cancer gene variants)
       - Example: "NAA10" (N-alpha-acetyltransferase variants)

    2. **Variant Names**: Protein or DNA change descriptions
       - Example: "p.Y402H" (tyrosine to histidine at position 402)
       - Example: "p.V600E" (valine to glutamic acid mutation)
       - Example: "c.1204T>C" (DNA change notation)

    3. **RSID Lookup**: Reference SNP identifiers from dbSNP
       - Example: "rs1061170" (CFH p.Y402H variant)
       - Example: "rs113488022" (BRAF p.V600E variant)
       - Example: "rs878853264" (rare variant example)

    4. **HGVS Notation**: Human Genome Variation Society standard
       - Example: "NM_000014.6:c.1204T>C" (transcript-specific)
       - Example: "p.Met1Val" (protein change notation)

    **Clinical Applications:**
    - Variant pathogenicity assessment for clinical genetics
    - Gene-disease association research and validation
    - Clinical variant interpretation workflows
    - Literature evidence gathering for variant reports
    - Population genetics and frequency analysis

    **Response Data:**
    Each variant result includes clinical significance classifications,
    publication counts for evidence assessment, database cross-references,
    and associated gene information for comprehensive variant characterization.

    **Performance Notes:**
    Results are cached using async LRU caching for improved response times.
    All queries respect LitVar2 API rate limits (2 requests/second).

    Args:
        query: Search query in any supported format (1-100 characters)
        limit: Maximum results to return (1-100, default 10)
        service: Injected variant service for database operations
        logger: Structured logging service for request tracking

    Returns:
        VariantSearchResponse with matching variants, metadata, and performance stats

    Raises:
        HTTPException(400): Invalid query parameters, format, or length
        HTTPException(422): Query validation errors or unsupported format
        HTTPException(502): LitVar2 API communication or rate limit errors
        HTTPException(500): Internal server error or unexpected failures
    """
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


@router.get(
    "/details/{variant_id}",
    summary="Get detailed variant information",
    description="Retrieve comprehensive information about a specific genetic variant by ID.",
    operation_id="get_variant_details",
    responses={
        200: {
            "description": "Detailed variant information retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "variant_id": "rs1061170",
                        "found": True,
                        "variant": {
                            "id": "rs1061170",
                            "gene": "CFH",
                            "hgvs_protein": "p.Y402H",
                            "clinical_significance": "pathogenic",
                            "publication_count": 127,
                            "allele_frequency": 0.23,
                        },
                        "cached": False,
                        "search_time_ms": 189,
                    },
                },
            },
        },
        404: {
            "description": "Variant not found in database",
            "content": {
                "application/json": {
                    "example": {
                        "variant_id": "rs999999999",
                        "found": False,
                        "variant": None,
                        "cached": True,
                        "search_time_ms": 45,
                    },
                },
            },
        },
        400: {
            "description": "Invalid variant ID format",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Invalid variant ID format. Expected RSID, gene symbol, or HGVS notation",
                    },
                },
            },
        },
    },
)
async def get_variant_details(
    variant_id: str = Path(
        ...,
        description="Variant identifier in any supported format",
        openapi_examples={
            "rsid_lookup": {
                "summary": "RSID variant lookup",
                "description": "Get details for CFH Y402H variant using reference SNP ID",
                "value": "rs1061170",
            },
            "braf_mutation": {
                "summary": "BRAF oncogene variant",
                "description": "Get details for BRAF V600E mutation (common in melanoma)",
                "value": "rs113488022",
            },
            "gene_variant": {
                "summary": "Gene-specific variant",
                "description": "Get details using gene symbol and protein change",
                "value": "BRCA1 p.Met1Val",
            },
            "hgvs_identifier": {
                "summary": "HGVS notation lookup",
                "description": "Get details using standard HGVS nomenclature",
                "value": "NM_000059.4:c.68A>G",
            },
        },
    ),
    *,
    service: ServiceDep,
    logger: LoggerDep,
) -> dict[str, Any]:
    """Retrieve comprehensive information about a specific genetic variant.

    This endpoint provides detailed variant information by performing a targeted
    search for the specified variant identifier and returning comprehensive
    metadata in a structured format.

    **Supported Identifier Types:**
    - **RSID**: Reference SNP IDs from dbSNP (e.g., "rs1061170")
    - **Gene Variants**: Gene symbol with protein change (e.g., "BRCA1 p.Met1Val")
    - **HGVS Notation**: Standard nomenclature (e.g., "NM_000059.4:c.68A>G")
    - **Protein Changes**: Amino acid substitutions (e.g., "p.Y402H")

    **Clinical Use Cases:**
    - Detailed variant characterization for clinical reports
    - Pathogenicity assessment and evidence review
    - Variant interpretation in diagnostic workflows
    - Research data collection and analysis
    - Cross-database variant validation

    **Response Structure:**
    The response includes a `found` boolean indicating variant availability,
    complete variant details when found, caching status for performance
    tracking, and search timing metrics.

    **Performance Optimization:**
    Searches utilize the same caching infrastructure as the search endpoint,
    providing fast responses for frequently accessed variants.

    Args:
        variant_id: Variant identifier in any supported format
        service: Injected variant service for database operations
        logger: Structured logging service for request tracking

    Returns:
        Dictionary containing variant details, availability status, and metadata

    Raises:
        HTTPException(400): Invalid variant ID format or unsupported identifier
        HTTPException(502): LitVar2 API communication or rate limit errors
        HTTPException(500): Internal server error or unexpected failures
    """
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
