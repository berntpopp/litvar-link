"""OpenAPI example payloads extracted from route handlers.

Pulling these large example dicts out of the decorators and parameter
declarations keeps the handler functions short (they were the dominant source
of route-file bloat). This module holds both the ``responses={...}`` payloads
and the per-parameter ``openapi_examples`` dicts referenced by ``Query``/``Path``.
"""

from __future__ import annotations

from typing import Any

# --- Parameter ``openapi_examples`` dicts (referenced by Query/Path) ---------

SEARCH_QUERY_EXAMPLES: dict[str, Any] = {
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
}

SEARCH_LIMIT_EXAMPLES: dict[str, Any] = {
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
}

VARIANT_DETAILS_ID_EXAMPLES: dict[str, Any] = {
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
}

GENE_NAME_EXAMPLES: dict[str, Any] = {
    "cfh_complement": {
        "summary": "Complement factor H gene",
        "description": "Get variants in complement factor H gene "
        "(major age-related macular degeneration gene)",
        "value": "CFH",
    },
    "brca1_oncology": {
        "summary": "BRCA1 tumor suppressor",
        "description": "Comprehensive variants in BRCA1 breast cancer gene",
        "value": "BRCA1",
    },
    "brca2_oncology": {
        "summary": "BRCA2 tumor suppressor",
        "description": "Get variants in BRCA2 hereditary breast cancer gene",
        "value": "BRCA2",
    },
    "naa10_rare": {
        "summary": "NAA10 acetyltransferase",
        "description": "N-alpha-acetyltransferase variants (LitVar2 example dataset)",
        "value": "NAA10",
    },
    "braf_oncogene": {
        "summary": "BRAF proto-oncogene",
        "description": "Get variants in BRAF gene (common in melanoma and other cancers)",
        "value": "BRAF",
    },
}

PUBLICATIONS_ID_EXAMPLES: dict[str, Any] = {
    "cfh_amd_variant": {
        "summary": "CFH Y402H AMD variant",
        "description": "Get publications for major age-related macular degeneration risk variant",
        "value": "rs1061170",
    },
    "braf_melanoma": {
        "summary": "BRAF V600E melanoma",
        "description": "Get publications for common BRAF mutation in melanoma research",
        "value": "rs113488022",
    },
    "brca1_founder": {
        "summary": "BRCA1 founder mutation",
        "description": "Get publications for Ashkenazi Jewish BRCA1 founder mutation",
        "value": "rs80357906",
    },
    "protein_notation": {
        "summary": "Protein change notation",
        "description": "Get publications using amino acid change description",
        "value": "p.V600E",
    },
    "gene_variant": {
        "summary": "Gene-specific variant",
        "description": "Get publications for gene symbol with protein change",
        "value": "CFH p.Y402H",
    },
}

SENSOR_RSID_EXAMPLES: dict[str, Any] = {
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
}

# --- ``responses={...}`` payloads --------------------------------------------

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
