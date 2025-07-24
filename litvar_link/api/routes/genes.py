"""Gene-related API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from litvar_link.exceptions import LitVarAPIError, ValidationError
from litvar_link.models import GeneVariantsResponse

from .dependencies import LoggerDep, ServiceDep

router = APIRouter(prefix="/api/genes", tags=["Genes"])


@router.get("/{gene_name}/variants", response_model=GeneVariantsResponse)
async def get_gene_variants(
    gene_name: str,
    service: ServiceDep = None,
    logger: LoggerDep = None,
) -> GeneVariantsResponse:
    """Get all variants associated with a specific gene.

    Returns comprehensive information about all genetic variants
    associated with the specified gene, including:
    - Complete list of variants with their details
    - Clinical significance statistics (pathogenic, benign, uncertain)
    - Publication counts for each variant
    - Variant classification and database flags

    This endpoint is useful for:
    - Gene-centric variant analysis
    - Clinical variant interpretation workflows
    - Research on gene-disease associations
    - Comprehensive variant cataloging

    Gene names should be official HUGO gene symbols (e.g., "CFH", "BRCA1").
    """
    try:
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

    except ValidationError as e:
        logger.warning("Validation error in gene variants", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except LitVarAPIError as e:
        logger.exception("API error in gene variants", error=str(e))
        raise HTTPException(status_code=502, detail="LitVar2 API error")
    except Exception as e:
        logger.error("Unexpected error in gene variants", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
