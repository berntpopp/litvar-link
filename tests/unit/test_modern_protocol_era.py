"""MCP 2026-07-28 (sessionless) protocol era over the real unified HTTP app."""

from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from litvar_link import server_manager
from litvar_link.config import settings

_HOST = "localhost"
_MODERN_VERSION = "2026-07-28"
_MODERN_META = {
    "io.modelcontextprotocol/protocolVersion": _MODERN_VERSION,
    "io.modelcontextprotocol/clientCapabilities": {},
    "io.modelcontextprotocol/clientInfo": {"name": "litvar-era-test", "version": "1.0.0"},
}
_BASE_HEADERS = {
    "accept": "application/json, text/event-stream",
    "content-type": "application/json",
    "host": _HOST,
}
_HOSTILE_METHOD = "evil__IGNORE_ALL_PREVIOUS__method"


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(settings, "allowed_hosts", [_HOST])
    application, _close_services = server_manager.create_unified_app()
    return TestClient(application, raise_server_exceptions=False)


def _modern_headers(method: str, *, name: str | None = None) -> dict[str, str]:
    headers = {**_BASE_HEADERS, "mcp-protocol-version": _MODERN_VERSION, "mcp-method": method}
    if name is not None:
        headers["mcp-name"] = name
    return headers


def _modern(client: TestClient, req_id: int, method: str, **params: Any) -> Any:
    return client.post(
        "/mcp",
        headers=_modern_headers(method, name=params.get("name")),
        json={
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": {"_meta": _MODERN_META, **params},
        },
    )


def test_modern_mcp_http_discovers_lists_calls_and_fences_unknown_tool(
    client: TestClient,
) -> None:
    hostile = "ignore-instructions-secret"
    with client:
        discover = _modern(client, 1, "server/discover")
        listed = _modern(client, 2, "tools/list")
        called = _modern(client, 3, "tools/call", name="get_server_capabilities", arguments={})
        unknown = _modern(client, 4, "tools/call", name=hostile, arguments={})

    assert discover.status_code == 200
    assert _MODERN_VERSION in discover.json()["result"]["supportedVersions"]
    assert "mcp-session-id" not in discover.headers
    assert listed.status_code == 200
    assert "get_server_capabilities" in {t["name"] for t in listed.json()["result"]["tools"]}
    called_result = called.json()["result"]
    assert json.loads(called_result["content"][0]["text"]) == called_result["structuredContent"]
    assert called_result["structuredContent"]["success"] is True
    unknown_result = unknown.json()["result"]
    assert unknown_result["isError"] is True
    assert unknown_result["structuredContent"]["error_code"] == "not_found"
    assert hostile not in unknown.text


def test_unknown_jsonrpc_method_is_not_reflected(client: TestClient) -> None:
    """SDK 2 echoes an unknown method in METHOD_NOT_FOUND ``data``; the guard strips it."""
    legacy_headers = {**_BASE_HEADERS, "mcp-protocol-version": "2025-06-18"}
    with client:
        client.post(
            "/mcp",
            headers=legacy_headers,
            json={
                "jsonrpc": "2.0",
                "id": 0,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "probe", "version": "0"},
                },
            },
        )
        legacy = client.post(
            "/mcp",
            headers=legacy_headers,
            json={"jsonrpc": "2.0", "id": 1, "method": _HOSTILE_METHOD, "params": {}},
        )
        modern = _modern(client, 2, _HOSTILE_METHOD)

    for resp in (legacy, modern):
        error = resp.json()["error"]
        assert error["code"] == -32601
        assert "data" not in error
        assert "evil" not in resp.text and "IGNORE" not in resp.text
