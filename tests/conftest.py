"""Pytest configuration and fixtures for LitVar-Link tests."""

import json
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient


@pytest.fixture
def sample_variant_data() -> Dict[str, Any]:
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
def sample_gene_variants_data() -> list[Dict[str, Any]]:
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
def sample_sensor_data() -> Dict[str, Any]:
    """Sample sensor response data."""
    return {
        "rsid": "rs1061170",
        "pmids_count": 834,
        "litvar_url": "https://www.ncbi.nlm.nih.gov/research/litvar2/docsum?text=rs1061170",
        "logo_url": "https://www.ncbi.nlm.nih.gov/research/litvar2/img/litvar_logo.png",
    }


@pytest.fixture
def sample_publication_data() -> list[str]:
    """Sample publication PMIDs."""
    return ["17634449", "18425111", "19060906", "20711173", "21602305"]


@pytest.fixture
def mock_httpx_client() -> AsyncMock:
    """Mock httpx AsyncClient for testing."""
    client = AsyncMock(spec=AsyncClient)
    return client


@pytest.fixture
def mock_litvar_client() -> MagicMock:
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
def sample_invalid_data() -> Dict[str, Any]:
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
            }
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
        headers: Dict[str, str] = None,
    ):
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
            raise HTTPStatusError("HTTP Error", request=request, response=response)


@pytest.fixture
def mock_response() -> MockResponse:
    """Create a mock response fixture."""
    return MockResponse
