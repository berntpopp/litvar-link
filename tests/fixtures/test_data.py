"""Test data fixtures and constants for LitVar-Link testing."""


class TestRSIDs:
    """Collection of test RSIDs for various scenarios."""

    # Valid RSIDs for different types of testing
    VALID_SINGLE = "rs1061170"
    VALID_MULTIPLE = ["rs1061170", "rs9970784", "rs878853264"]
    VALID_LARGE_SET = [f"rs{i}" for i in range(1000000, 1000050)]  # 50 RSIDs

    # RSIDs with known characteristics
    WITH_HIGH_PUBLICATIONS = "rs1061170"  # 834 publications
    WITH_LOW_PUBLICATIONS = "rs9970784"  # 1 publication
    PATHOGENIC_VARIANT = "rs878853264"  # BRCA1 pathogenic
    BENIGN_VARIANT = "rs800292"  # CFH benign

    # Edge cases
    INVALID_FORMAT = ["abc123", "not_an_rsid", "", "rs", "1061170"]
    NON_EXISTENT = ["rs999999999", "rs000000000"]
    MIXED_VALID_INVALID = ["rs1061170", "invalid_rsid", "rs9970784"]


class TestGeneSymbols:
    """Collection of test gene symbols for various scenarios."""

    # Valid gene symbols
    VALID_SINGLE = "CFH"
    VALID_MULTIPLE = ["CFH", "BRCA1", "BRCA2", "NAA10"]

    # Genes with known variant characteristics
    HIGH_VARIANT_COUNT = "CFH"  # Many variants
    LOW_VARIANT_COUNT = "NAA10"  # Few variants
    CANCER_GENE = "BRCA1"  # Cancer susceptibility
    RARE_DISEASE_GENE = "NAA10"  # Rare disease

    # Invalid gene symbols
    INVALID_FORMAT = ["", "gene_123", "INVALID*GENE", "a" * 51]
    NON_EXISTENT = ["NONEXISTENTGENE", "FAKEGENE123"]
    MIXED_VALID_INVALID = ["CFH", "invalid_gene", "BRCA1"]


class TestVariantQueries:
    """Collection of test variant search queries."""

    # Gene-based queries
    GENE_QUERIES = [
        "CFH",
        "BRCA1",
        "BRCA2",
        "NAA10",
    ]

    # Variant nomenclature queries
    HGVS_QUERIES = [
        "BRCA1 p.Met1Val",
        "CFH p.Y402H",
        "BRCA2 c.317-1G>A",
        "NAA10 c.109A>T",
    ]

    # RSID queries
    RSID_QUERIES = [
        "rs1061170",
        "rs9970784",
        "rs878853264",
    ]

    # Complex queries
    COMPLEX_QUERIES = [
        "BRCA1 pathogenic mutations",
        "CFH age-related macular degeneration",
        "NAA10 intellectual disability",
    ]

    # Edge case queries
    EDGE_CASES = [
        "",  # Empty query
        "a",  # Single character
        "a" * 100,  # Maximum length
        "query with spaces",  # Spaces
        "query-with-hyphens",  # Hyphens
        "query_with_underscores",  # Underscores
        "QUERY WITH CAPS",  # All caps
        "MiXeD cAsE qUeRy",  # Mixed case
        "query123",  # Numbers
        "β-globin",  # Unicode
    ]


class TestVariantIDs:
    """Collection of test variant IDs for various scenarios."""

    # Valid LitVar2 format IDs
    VALID_RSID_FORMAT = [
        "litvar@rs1061170##",
        "litvar@rs9970784##",
        "litvar@rs878853264##",
    ]

    VALID_GENOMIC_FORMAT = [
        "litvar@CFH@g.3572C>T##",
        "litvar@NAA10@c.109A>T##",
        "litvar@BRCA1@c.68_69delAG##",
    ]

    # Invalid formats
    INVALID_FORMAT = [
        "",  # Empty
        "rs1061170",  # Missing litvar prefix
        "litvar@rs1061170",  # Missing suffix
        "@rs1061170##",  # Missing litvar
        "litvar@##",  # Missing variant
        "invalid_format",  # Random string
    ]


class TestLimits:
    """Collection of test limit values."""

    # Valid limits
    VALID_LIMITS = [1, 5, 10, 20, 50, 100]
    DEFAULT_LIMIT = 10
    MIN_LIMIT = 1
    MAX_LIMIT = 100

    # Invalid limits
    INVALID_LIMITS = [0, -1, 101, 1000, -10]


class TestClinicalSignificance:
    """Collection of clinical significance values."""

    # Valid clinical significance terms
    VALID_TERMS = [
        "pathogenic",
        "likely pathogenic",
        "uncertain significance",
        "likely benign",
        "benign",
        "risk factor",
        "protective",
        "affects",
        "association",
        "drug response",
    ]

    # Invalid terms
    INVALID_TERMS = [
        "",
        "invalid_significance",
        "unknown",
        "not_applicable",
    ]


class TestPerformanceData:
    """Collection of performance testing data."""

    # Concurrent request configurations
    LOAD_TEST_CONFIGS = [
        {"users": 5, "requests_per_user": 10, "max_response_time": 2.0},
        {"users": 10, "requests_per_user": 20, "max_response_time": 5.0},
        {"users": 25, "requests_per_user": 50, "max_response_time": 10.0},
    ]

    # Rate limiting test data (LitVar2: 2 req/sec)
    RATE_LIMIT_TESTS = [
        {"requests": 2, "timespan": 1.0, "should_pass": True},  # Within limit
        {"requests": 4, "timespan": 1.0, "should_pass": False},  # Exceeds limit
        {"requests": 10, "timespan": 5.0, "should_pass": True},  # Distributed over time
    ]

    # Large dataset tests
    LARGE_DATASETS = {
        "rsids_100": [f"rs{i}" for i in range(1000000, 1000100)],
        "rsids_500": [f"rs{i}" for i in range(1000000, 1000500)],
        "queries_batch": [f"query_{i}" for i in range(1, 101)],
        "genes_batch": [f"GENE{i}" for i in range(1, 51)],
    }


class TestErrorScenarios:
    """Collection of error testing scenarios."""

    # HTTP status code scenarios
    ERROR_SCENARIOS = [
        {"status": 400, "type": "validation", "message": "Invalid request parameters"},
        {"status": 404, "type": "not_found", "message": "Variant not found"},
        {"status": 422, "type": "unprocessable", "message": "Validation error"},
        {"status": 429, "type": "rate_limit", "message": "Rate limit exceeded"},
        {"status": 500, "type": "server_error", "message": "Internal server error"},
        {"status": 503, "type": "unavailable", "message": "Service unavailable"},
        {"status": 504, "type": "timeout", "message": "Request timeout"},
    ]

    # Network error scenarios
    NETWORK_ERRORS = [
        "ConnectionError",
        "TimeoutError",
        "HTTPError",
        "RequestException",
        "DNSError",
    ]


class TestValidationCases:
    """Collection of validation test cases."""

    # Parameter validation tests
    VALIDATION_TESTS = [
        # RSID validation
        {"input": "rs1061170", "valid": True, "type": "rsid"},
        {"input": "invalid_rsid", "valid": False, "type": "rsid"},
        {"input": "", "valid": False, "type": "rsid"},
        {"input": "rs", "valid": False, "type": "rsid"},
        {"input": "1061170", "valid": False, "type": "rsid"},
        # Gene name validation
        {"input": "CFH", "valid": True, "type": "gene"},
        {"input": "BRCA1", "valid": True, "type": "gene"},
        {"input": "", "valid": False, "type": "gene"},
        {"input": "a" * 51, "valid": False, "type": "gene"},
        # Query validation
        {"input": "CFH p.Y402H", "valid": True, "type": "query"},
        {"input": "BRCA1", "valid": True, "type": "query"},
        {"input": "", "valid": False, "type": "query"},
        {"input": "   ", "valid": False, "type": "query"},
        {"input": "a" * 101, "valid": False, "type": "query"},
        # Limit validation
        {"input": 10, "valid": True, "type": "limit"},
        {"input": 1, "valid": True, "type": "limit"},
        {"input": 100, "valid": True, "type": "limit"},
        {"input": 0, "valid": False, "type": "limit"},
        {"input": -1, "valid": False, "type": "limit"},
        {"input": 101, "valid": False, "type": "limit"},
        # Variant ID validation
        {"input": "litvar@rs1061170##", "valid": True, "type": "variant_id"},
        {"input": "litvar@CFH@g.3572C>T##", "valid": True, "type": "variant_id"},
        {"input": "", "valid": False, "type": "variant_id"},
        {"input": "rs1061170", "valid": False, "type": "variant_id"},
    ]


class TestCacheScenarios:
    """Collection of cache testing scenarios."""

    # Cache keys for different operations
    CACHE_KEYS = {
        "variant_search": "variant_search:CFH:10",
        "gene_variants": "gene_variants:CFH",
        "sensor_lookup": "sensor_lookup:rs1061170",
        "variant_literature": "variant_literature:litvar@rs1061170##",
    }

    # Cache patterns for selective clearing
    CACHE_PATTERNS = [
        "variant_search:",
        "gene_variants:",
        "sensor_lookup:",
        "variant_literature:",
    ]

    # TTL test scenarios
    TTL_SCENARIOS = [
        {"ttl": 1, "wait": 0.5, "should_be_cached": True},  # Within TTL
        {"ttl": 1, "wait": 1.5, "should_be_cached": False},  # After TTL
        {"ttl": 300, "wait": 0.1, "should_be_cached": True},  # Long TTL
    ]


# Test configuration constants
TEST_CONFIG = {
    "default_timeout": 30.0,
    "max_retries": 3,
    "rate_limit_per_second": 2.0,  # LitVar2 rate limit
    "cache_ttl_seconds": 300,
    "max_query_length": 100,
    "max_gene_name_length": 50,
    "max_limit": 100,
    "min_limit": 1,
    "default_limit": 10,
}
