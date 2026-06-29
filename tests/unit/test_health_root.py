"""Unit test: GET /health returns {status, version, transport} (MCP Transport Standard v1).

The conformance probe (tests/conformance/test_transport_v1.py) checks
``GET {base}/health`` → 200 with ``status``, ``version``, and ``transport``
keys. This test locks in the contract without requiring a live server.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

import litvar_link.app as app_module
from litvar_link import __version__


def test_health_endpoint_returns_200() -> None:
    """GET /health must return HTTP 200."""
    app = app_module.create_app()
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200


def test_health_has_status_version_transport() -> None:
    """GET /health body must carry status, version, and transport keys."""
    app = app_module.create_app()
    client = TestClient(app)
    body = client.get("/health").json()
    assert "status" in body, f"missing 'status' in {body}"
    assert "version" in body, f"missing 'version' in {body}"
    assert "transport" in body, f"missing 'transport' in {body}"


def test_health_version_matches_package() -> None:
    """version field must equal the installed package version."""
    app = app_module.create_app()
    client = TestClient(app)
    body = client.get("/health").json()
    assert body["version"] == __version__


def test_health_transport_is_stateless() -> None:
    """transport field must be 'streamable-http-stateless'."""
    app = app_module.create_app()
    client = TestClient(app)
    body = client.get("/health").json()
    assert body["transport"] == "streamable-http-stateless"
