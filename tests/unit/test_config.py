"""Config smoke test: nested env vars map to nested pydantic-settings models."""

from __future__ import annotations

import pytest

from litvar_link.config import ServerSettings


@pytest.fixture
def nested_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LITVAR_LINK_API__BASE_URL", "https://example.test/api")
    monkeypatch.setenv("LITVAR_LINK_API__TIMEOUT", "17")
    monkeypatch.setenv("LITVAR_LINK_CACHE__TTL", "120")
    monkeypatch.setenv("LITVAR_LINK_CACHE__SIZE", "42")


def test_nested_env_maps_to_models(nested_env: None) -> None:
    settings = ServerSettings(_env_file=None)
    # base_url validator appends a trailing slash
    assert settings.api.base_url == "https://example.test/api/"
    assert settings.api.timeout == 17
    assert settings.cache.ttl == 120
    assert settings.cache.size == 42


def test_flat_top_level_still_works(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LITVAR_LINK_PORT", "9001")
    settings = ServerSettings(_env_file=None)
    assert settings.port == 9001
