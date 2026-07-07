"""Security guard: the unauthenticated backend must not enable CORS credentials.

This backend holds no cookies or session, so ``Access-Control-Allow-Credentials:
true`` is meaningless and a footgun if origins are ever widened to ``*``.
Credentials default OFF, the existing method list is preserved (several routes
serve GET, e.g. ``/health``), and the app refuses to start if credentials are
re-enabled alongside a wildcard origin. Research use only; not clinical decision
support."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import litvar_link.app as app_module
from litvar_link.config import ServerSettings


def test_cors_credentials_disabled_by_default() -> None:
    """Credentials must default to OFF for the unauthenticated backend."""
    assert ServerSettings(_env_file=None).cors_allow_credentials is False


def test_cors_middleware_configured_without_credentials() -> None:
    """The wired CORS middleware must set allow_credentials=False."""
    app = app_module.create_app()
    cors = next(mw for mw in app.user_middleware if mw.cls.__name__ == "CORSMiddleware")
    assert cors.kwargs["allow_credentials"] is False


def test_health_ok_without_credentialed_cors_header() -> None:
    """GET /health stays 200 and never emits a credentialed CORS header."""
    client = TestClient(app_module.create_app())
    resp = client.get("/health", headers={"Origin": "http://localhost:3000"})
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-credentials") != "true"


def test_existing_method_list_preserved() -> None:
    """Preserve the repo's method list (do NOT collapse to POST-only)."""
    methods = ServerSettings(_env_file=None).cors_allow_methods
    assert "GET" in methods and "POST" in methods


def test_startup_rejects_credentials_with_wildcard_origin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fail closed: credentials + a wildcard origin must abort app startup."""
    monkeypatch.setattr(app_module.settings, "cors_allow_credentials", True)
    monkeypatch.setattr(app_module.settings, "cors_origins", ["*"])
    with pytest.raises(RuntimeError, match="CORS"):
        app_module.create_app()
