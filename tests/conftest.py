"""Pytest configuration and fixtures for LitVar-Link tests."""

import asyncio
import json
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import AsyncClient

from litvar_link.api.client import LitVar2Client
from litvar_link.config import settings
from litvar_link.server_manager import UnifiedServerManager
from litvar_link.services.variant_service import VariantService


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_logger():
    """Mock logger for testing."""
    logger = Mock()
    logger.info = Mock()
    logger.error = Mock()
    logger.warning = Mock()
    logger.debug = Mock()
    return logger


@pytest.fixture
def mock_litvar_client():
    """Mock LitVar2Client for testing."""
    client = AsyncMock(spec=LitVar2Client)

    # Configure default return values
    client.search_variants = AsyncMock()
    client.get_variant_details = AsyncMock()
    client.get_variant_publications = AsyncMock()
    client.sensor_lookup = AsyncMock()
    client.get_variants_by_gene = AsyncMock()

    return client


@pytest.fixture
def mock_variant_service(mock_litvar_client, mock_logger):
    """Mock VariantService for testing."""
    service = Mock(spec=VariantService)
    service.client = mock_litvar_client
    service.logger = mock_logger

    # Configure async methods
    service.search_variants = AsyncMock()
    service.lookup_rsid = AsyncMock()
    service.search_gene_variants = AsyncMock()
    service.get_variant_literature = AsyncMock()
    service.cache_stats = Mock(
        return_value={
            "hits": 0,
            "misses": 0,
            "hit_rate": 0.0,
            "total_requests": 0,
        },
    )

    return service


@pytest.fixture
def facade():
    """A FastMCP facade built like the explicit server, for tool-surface tests."""
    from litvar_link.mcp.facade import create_litvar_mcp

    return create_litvar_mcp(service_factory=lambda: object())


@pytest.fixture
def app():
    """Create FastAPI application instance for testing."""
    manager = UnifiedServerManager()
    return manager.create_app()


@pytest.fixture
def test_client(app):
    """Create TestClient for FastAPI application."""
    return TestClient(app)


@pytest.fixture
async def async_client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """Create async HTTP client for testing."""
    from httpx import ASGITransport

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


@pytest.fixture
def sample_variant_data() -> dict[str, Any]:
    """Sample variant data from LitVar2 API autocomplete response."""
    return {
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
    }


@pytest.fixture
def sample_gene_variants_data() -> list[dict[str, Any]]:
    """Sample gene variants data from LitVar2 API."""
    return [
        {
            "_id": "litvar@rs9970784##",
            "rsid": "rs9970784",
            "gene": ["CFH"],
            "name": "p.R661A",
            "pmids_count": 1,
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
        },
    ]


@pytest.fixture
def sample_sensor_data() -> dict[str, Any]:
    """Sample sensor response data (matches the real LitVar2 sensor payload shape).

    The real sensor endpoint returns {pmids_count, rsid, link, logo} -- NOT
    litvar_url/variant_id/gene/variant_name. Those three id fields are enriched
    from autocomplete by lookup_rsid (issue #20).
    """
    return {
        "pmids_count": 834,
        "rsid": "rs1061170",
        "link": (
            "https://www.ncbi.nlm.nih.gov/research/litvar2/docsum"
            "?variant=litvar%40rs1061170%23%23&query=rs1061170"
        ),
        "logo": "https://www.ncbi.nlm.nih.gov/research/litvar2/assets/litvar-logo-small.png",
    }


@pytest.fixture
def sample_publication_data() -> list[str]:
    """Sample publication PMIDs."""
    return ["17634449", "18425111", "19060906", "20711173", "21602305"]


@pytest.fixture
def mock_httpx_client() -> AsyncMock:
    """Mock httpx AsyncClient for testing."""
    return AsyncMock(spec=AsyncClient)


@pytest.fixture
def mock_litvar_client_v2() -> MagicMock:
    """Mock LitVar2 client for testing."""
    client = MagicMock()

    # Setup async context manager
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)

    # Setup async methods
    client.search_variants = AsyncMock()
    client.get_variant_details = AsyncMock()
    client.get_variant_publications = AsyncMock()
    client.sensor_lookup = AsyncMock()
    client.get_variants_by_gene = AsyncMock()

    return client


@pytest.fixture
def sample_invalid_data() -> dict[str, Any]:
    """Sample invalid data for testing validation."""
    return {
        "_id": "",  # Empty ID
        "rsid": "invalid_rsid",  # Invalid RSID format
        "gene": [""],  # Empty gene list
        "pmids_count": -5,  # Negative count
        "data_clinical_significance": ["invalid_significance"],
    }


@pytest.fixture(scope="session", autouse=True)
def configure_test_environment() -> None:
    """Configure test environment settings."""
    import os

    # Set test environment variables
    os.environ["LITVAR_LINK_LOG_LEVEL"] = "DEBUG"
    os.environ["LITVAR_LINK_CACHE_SIZE"] = "100"
    os.environ["LITVAR_LINK_CACHE_TTL"] = "300"


@pytest.fixture
def json_response_data() -> str:
    """Sample JSON response for testing JSON parsing."""
    data = {
        "variants": [
            {
                "_id": "test_variant_1",
                "rsid": "rs123456",
                "gene": ["TEST1"],
                "name": "p.A123B",
                "pmids_count": 5,
            },
        ],
        "total_count": 1,
    }
    return json.dumps(data)


class MockResponse:
    """Mock HTTP response for testing."""

    def __init__(
        self,
        json_data: Any = None,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
    ):
        """Initialize mock response."""
        self.json_data = json_data
        self.status_code = status_code
        self.headers = headers or {"content-type": "application/json"}
        self.text = json.dumps(json_data) if json_data else ""

    def json(self) -> Any:
        """Return JSON data."""
        return self.json_data

    def raise_for_status(self) -> None:
        """Raise exception for bad status codes."""
        if self.status_code >= 400:
            from httpx import HTTPStatusError, Request, Response

            request = Request("GET", "http://test.com")
            response = Response(self.status_code)
            msg = "HTTP Error"
            raise HTTPStatusError(msg, request=request, response=response)


@pytest.fixture
def mock_response() -> MockResponse:
    """Create a mock response fixture."""
    return MockResponse


@pytest.fixture
def mock_rate_limiter():
    """Mock rate limiter for testing."""
    with patch("litvar_link.api.client.AsyncLimiter") as mock_limiter:
        limiter_instance = AsyncMock()
        mock_limiter.return_value = limiter_instance
        yield limiter_instance


@pytest.fixture(autouse=True)
def override_settings():
    """Override settings for testing."""
    original_values = {}
    test_settings = {
        "log_level": "DEBUG",
        "cache_ttl": 60,  # Short TTL for testing
        "rate_limit": 10,  # Higher rate limit for testing
        "litvar_base_url": "https://test.litvar2.org",
    }

    # Store original values and set test values
    for key, value in test_settings.items():
        if hasattr(settings, key):
            original_values[key] = getattr(settings, key)
            setattr(settings, key, value)

    yield

    # Restore original values
    for key, value in original_values.items():
        setattr(settings, key, value)


# Error fixtures for testing error handling
@pytest.fixture
def api_error():
    """Sample API error for testing."""
    return {
        "error": "Invalid request",
        "message": "The provided query parameters are not valid",
        "status": 400,
    }


@pytest.fixture
def rate_limit_error():
    """Sample rate limit error for testing."""
    return {
        "error": "Rate limit exceeded",
        "message": "Too many requests. Please wait before trying again.",
        "status": 429,
    }


# Test data fixtures from fixtures/test_data.py
@pytest.fixture
def valid_rsids() -> list[str]:
    """Return valid RSIDs for testing."""
    from tests.fixtures.test_data import TestRSIDs

    return TestRSIDs.VALID_MULTIPLE


@pytest.fixture
def valid_gene_symbols() -> list[str]:
    """Return valid gene symbols for testing."""
    from tests.fixtures.test_data import TestGeneSymbols

    return TestGeneSymbols.VALID_MULTIPLE


@pytest.fixture
def valid_limits() -> list[int]:
    """Return valid limit values for testing."""
    from tests.fixtures.test_data import TestLimits

    return TestLimits.VALID_LIMITS


# Performance test fixtures
@pytest.fixture
def large_rsid_list() -> list[str]:
    """Large list of RSIDs for performance testing."""
    from tests.fixtures.test_data import TestPerformanceData

    return TestPerformanceData.LARGE_DATASETS["rsids_100"]


@pytest.fixture
def concurrent_requests():
    """Return configuration for concurrent request testing."""
    from tests.fixtures.test_data import TestPerformanceData

    return TestPerformanceData.LOAD_TEST_CONFIGS[0]
