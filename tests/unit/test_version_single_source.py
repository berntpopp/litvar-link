"""Guard: pyproject -> installed metadata -> __version__ -> serverInfo are one value."""

from __future__ import annotations

import tomllib
from importlib.metadata import version
from pathlib import Path

from litvar_link import __version__
from litvar_link.mcp.facade import create_litvar_mcp

DIST = "litvar-link"


def _pyproject_version() -> str:
    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    return tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]["version"]


def test_pyproject_is_the_single_source() -> None:
    assert version(DIST) == _pyproject_version()


def test_dunder_version_is_metadata_derived() -> None:
    assert __version__ == version(DIST)


def test_mcp_server_info_version_matches_package() -> None:
    mcp = create_litvar_mcp(service_factory=lambda: object())
    assert mcp.version == version(DIST)
