"""Mock API response fixtures for LitVar2 API testing."""

from typing import Any


class MockLitVarResponses:
    """Collection of mock LitVar2 API responses for testing."""

    @staticmethod
    def variant_autocomplete_response() -> list[dict[str, Any]]:
        """Mock variant autocomplete response."""
        return [
            {
                "_id": "litvar@rs1061170##",
                "rsid": "rs1061170",
                "gene": ["CFH"],
                "name": "p.Y402H",
                "hgvs": "NP_000177.2:p.Tyr402His",
                "pmids_count": 834,
                "data_clinical_significance": ["risk factor", "benign"],
                "flag_gene_variant": True,
                "flag_clingen_variant": False,
                "flag_rsid_variant": True,
                "match": "CFH <em>p.Y402H</em> (rs1061170)",
            },
            {
                "_id": "litvar@rs878853264##",
                "rsid": "rs878853264",
                "gene": ["BRCA1"],
                "name": "p.Met1Val",
                "hgvs": "NP_009225.1:p.Met1Val",
                "pmids_count": 12,
                "data_clinical_significance": ["pathogenic"],
                "flag_gene_variant": True,
                "flag_clingen_variant": True,
                "flag_rsid_variant": True,
                "match": "BRCA1 <em>p.Met1Val</em> (rs878853264)",
            },
            {
                "_id": "litvar@NAA10@c.109A>T##",
                "gene": ["NAA10"],
                "name": "c.109A>T",
                "pmids_count": 3,
                "data_clinical_significance": ["uncertain significance"],
                "flag_gene_variant": True,
                "flag_clingen_variant": False,
                "flag_rsid_variant": False,
                "match": "NAA10 <em>c.109A>T</em>",
            },
        ]

    @staticmethod
    def gene_variants_response() -> list[dict[str, Any]]:
        """Mock gene variants response."""
        return [
            {
                "_id": "litvar@rs9970784##",
                "rsid": "rs9970784",
                "gene": ["CFH"],
                "name": "p.R661A",
                "pmids_count": 1,
                "data_clinical_significance": ["benign"],
            },
            {
                "_id": "litvar@rs800292##",
                "rsid": "rs800292",
                "gene": ["CFH"],
                "name": "p.I62V",
                "pmids_count": 490,
                "data_clinical_significance": ["benign"],
            },
            {
                "_id": "litvar@CFH@g.3572C>T##",
                "gene": ["CFH"],
                "name": "g.3572C>T",
                "pmids_count": 2,
                "data_clinical_significance": ["pathogenic"],
            },
            {
                "_id": "litvar@rs1061170##",
                "rsid": "rs1061170",
                "gene": ["CFH"],
                "name": "p.Y402H",
                "pmids_count": 834,
                "data_clinical_significance": ["risk factor", "benign"],
            },
        ]

    @staticmethod
    def sensor_response_available() -> dict[str, Any]:
        """Mock sensor response for available variant."""
        return {
            "rsid": "rs1061170",
            "pmids_count": 834,
            "litvar_url": "https://www.ncbi.nlm.nih.gov/research/litvar2/docsum?text=rs1061170",
            "logo_url": "https://www.ncbi.nlm.nih.gov/research/litvar2/img/litvar_logo.png",
        }

    @staticmethod
    def sensor_response_not_available() -> None:
        """Mock sensor response for unavailable variant."""
        return None

    @staticmethod
    def publications_response() -> list[str]:
        """Mock publications response."""
        return ["17634449", "18425111", "19060906", "20711173", "21602305"]

    @staticmethod
    def empty_response() -> list:
        """Mock empty response."""
        return []


class MockErrorResponses:
    """Collection of mock error responses for testing."""

    @staticmethod
    def rate_limit_error() -> dict[str, Any]:
        """Mock rate limit error response."""
        return {
            "error": "Rate limit exceeded",
            "message": "Too many requests. Please wait 60 seconds before trying again.",
            "status": 429,
            "retry_after": 60,
        }

    @staticmethod
    def not_found_error() -> dict[str, Any]:
        """Mock not found error response."""
        return {
            "error": "Not found",
            "message": "The requested variant was not found in LitVar2",
            "status": 404,
        }

    @staticmethod
    def validation_error() -> dict[str, Any]:
        """Mock validation error response."""
        return {
            "error": "Validation error",
            "message": "Invalid request parameters provided",
            "status": 422,
            "details": {
                "query": ["Query cannot be empty"],
                "limit": ["Limit must be between 1 and 100"],
            },
        }

    @staticmethod
    def server_error() -> dict[str, Any]:
        """Mock internal server error response."""
        return {
            "error": "Internal server error",
            "message": "An unexpected error occurred while processing your request",
            "status": 500,
        }

    @staticmethod
    def service_unavailable_error() -> dict[str, Any]:
        """Mock service unavailable error response."""
        return {
            "error": "Service unavailable",
            "message": "LitVar2 service is temporarily unavailable",
            "status": 503,
        }

    @staticmethod
    def timeout_error() -> dict[str, Any]:
        """Mock timeout error response."""
        return {
            "error": "Request timeout",
            "message": "Request to LitVar2 API timed out",
            "status": 504,
        }


class MockCacheResponses:
    """Collection of mock cache-related responses for testing."""

    @staticmethod
    def cache_statistics() -> dict[str, Any]:
        """Mock cache statistics response."""
        return {
            "total_size": 150,
            "current_size": 45,
            "hit_rate": 0.672,
            "miss_rate": 0.328,
            "total_hits": 234,
            "total_misses": 114,
            "detailed_stats": {
                "variant_search": {
                    "size": 15,
                    "hits": 89,
                    "misses": 23,
                    "hit_rate": 0.795,
                },
                "gene_variants": {
                    "size": 12,
                    "hits": 67,
                    "misses": 18,
                    "hit_rate": 0.788,
                },
                "sensor_lookup": {
                    "size": 18,
                    "hits": 78,
                    "misses": 73,
                    "hit_rate": 0.517,
                },
            },
        }

    @staticmethod
    def cache_clear_response() -> dict[str, Any]:
        """Mock cache clear response."""
        return {
            "success": True,
            "message": "Cache cleared successfully",
            "cleared_items": 45,
            "pattern": None,
        }
