"""app.py no longer carries the from_fastapi MCP path or the buggy name map."""

from __future__ import annotations

import litvar_link.app as app_module


def test_app_has_no_create_mcp_app() -> None:
    assert not hasattr(app_module, "create_mcp_app")
    assert not hasattr(app_module, "mcp_app")


def test_app_source_has_no_mcp_custom_names() -> None:
    import inspect

    src = inspect.getsource(app_module)
    assert "mcp_custom_names" not in src
    assert "from_fastapi" not in src


def test_create_app_still_builds() -> None:
    app = app_module.create_app()
    # FastAPI 0.137 records included routers as ``_IncludedRouter`` proxies in
    # ``app.routes`` rather than flattening child routes, so assert against the
    # public OpenAPI schema (the stable contract) instead of route internals.
    assert "/api/health/" in app.openapi().get("paths", {})
