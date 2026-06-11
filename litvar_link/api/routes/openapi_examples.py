"""OpenAPI ``responses={...}`` example payloads extracted from route handlers.

Pulling these large example dicts out of the decorators keeps the handler
functions short (they were the dominant source of route-file bloat).
"""

from __future__ import annotations

from typing import Any

SEARCH_RESPONSES: dict[int | str, dict[str, Any]] = {
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
}

VARIANT_DETAILS_RESPONSES: dict[int | str, dict[str, Any]] = {
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
}

PUBLICATIONS_RESPONSES: dict[int | str, dict[str, Any]] = {
    200: {
        "description": "Publications retrieved successfully with metadata",
        "content": {
            "application/json": {
                "example": {
                    "variant_id": "rs1061170",
                    "total_count": 127,
                    "publications": [
                        {
                            "pmid": "32511357",
                            "pmcid": "PMC7279073",
                            "title": "Complement factor H Y402H polymorphism and age-related macular degeneration",
                            "journal": "Nature Genetics",
                            "publication_year": 2020,
                            "study_type": "genome-wide association study",
                        },
                        {
                            "pmid": "29355051",
                            "title": "CFH variants and AMD risk in European populations",
                            "journal": "Human Genetics",
                            "publication_year": 2018,
                            "study_type": "meta-analysis",
                        },
                    ],
                    "journal_distribution": {
                        "Nature Genetics": 23,
                        "Human Genetics": 18,
                        "PLOS Genetics": 15,
                    },
                    "cached": False,
                    "search_time_ms": 341,
                },
            },
        },
    },
    404: {
        "description": "No publications found for variant",
        "content": {
            "application/json": {
                "example": {
                    "variant_id": "rs999999999",
                    "total_count": 0,
                    "publications": [],
                    "message": "No publications found for variant rs999999999",
                },
            },
        },
    },
    400: {
        "description": "Invalid variant identifier format",
        "content": {
            "application/json": {
                "example": {
                    "detail": "Invalid variant ID format. Expected RSID, gene symbol, or HGVS notation",
                },
            },
        },
    },
    502: {
        "description": "LitVar2 API communication error",
        "content": {
            "application/json": {"example": {"detail": "LitVar2 API error"}},
        },
    },
}

GENE_VARIANTS_RESPONSES: dict[int | str, dict[str, Any]] = {
    200: {
        "description": "Gene variants retrieved successfully with statistics",
        "content": {
            "application/json": {
                "example": {
                    "gene_name": "CFH",
                    "total_count": 234,
                    "pathogenic_count": 45,
                    "benign_count": 123,
                    "uncertain_count": 66,
                    "variants": [
                        {
                            "id": "rs1061170",
                            "hgvs_protein": "p.Y402H",
                            "clinical_significance": "pathogenic",
                            "publication_count": 127,
                            "allele_frequency": 0.23,
                        },
                        {
                            "id": "rs9970784",
                            "hgvs_protein": "p.I62V",
                            "clinical_significance": "benign",
                            "publication_count": 34,
                            "allele_frequency": 0.45,
                        },
                    ],
                    "cached": False,
                    "search_time_ms": 567,
                },
            },
        },
    },
    400: {
        "description": "Invalid gene symbol format",
        "content": {
            "application/json": {
                "example": {
                    "detail": "Invalid gene symbol. Must be a valid HUGO gene symbol",
                },
            },
        },
    },
    404: {
        "description": "Gene not found or no variants available",
        "content": {
            "application/json": {
                "example": {
                    "gene_name": "NONEXISTENT",
                    "total_count": 0,
                    "variants": [],
                    "message": "No variants found for gene NONEXISTENT",
                },
            },
        },
    },
    502: {
        "description": "LitVar2 API communication error",
        "content": {
            "application/json": {"example": {"detail": "LitVar2 API error"}},
        },
    },
}

SENSOR_RESPONSES: dict[int | str, dict[str, Any]] = {
    200: {
        "description": "RSID availability check completed successfully",
        "content": {
            "application/json": {
                "examples": {
                    "available_rsid": {
                        "summary": "Available RSID with variant data",
                        "value": {
                            "rsid": "rs1061170",
                            "available": True,
                            "variant_info": {
                                "gene": "CFH",
                                "hgvs_protein": "p.Y402H",
                                "clinical_significance": "pathogenic",
                            },
                            "cached": False,
                            "response_time_ms": 123,
                        },
                    },
                    "unavailable_rsid": {
                        "summary": "RSID not found in database",
                        "value": {
                            "rsid": "rs999999999",
                            "available": False,
                            "variant_info": None,
                            "cached": True,
                            "response_time_ms": 45,
                        },
                    },
                },
            },
        },
    },
    400: {
        "description": "Invalid RSID format",
        "content": {
            "application/json": {
                "example": {
                    "detail": "Invalid RSID format. Must start with 'rs' followed by digits (e.g., rs1061170)",
                },
            },
        },
    },
    502: {
        "description": "LitVar2 API communication error",
        "content": {
            "application/json": {"example": {"detail": "LitVar2 API error"}},
        },
    },
}
