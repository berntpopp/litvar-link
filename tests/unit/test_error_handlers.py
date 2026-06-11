"""Exception handlers map domain errors to HTTP status codes (DRY cluster #3)."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from litvar_link.api.error_handlers import register_exception_handlers
from litvar_link.exceptions import LitVarAPIError, ValidationError


def _client() -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/boom-validation")
    async def boom_validation() -> dict[str, str]:
        raise ValidationError("bad query", field="query")

    @app.get("/boom-api")
    async def boom_api() -> dict[str, str]:
        raise LitVarAPIError("upstream blew up", status_code=500)

    @app.get("/boom-unexpected")
    async def boom_unexpected() -> dict[str, str]:
        raise RuntimeError("kaboom")

    return TestClient(app, raise_server_exceptions=False)


def test_validation_error_maps_to_400() -> None:
    resp = _client().get("/boom-validation")
    assert resp.status_code == 400
    assert resp.json()["detail"] == "bad query"


def test_litvar_api_error_maps_to_502() -> None:
    resp = _client().get("/boom-api")
    assert resp.status_code == 502
    assert resp.json()["detail"] == "LitVar2 API error"


def test_unexpected_error_maps_to_500() -> None:
    resp = _client().get("/boom-unexpected")
    assert resp.status_code == 500
    assert resp.json()["detail"] == "Internal server error"
