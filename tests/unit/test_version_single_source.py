"""Guard: pyproject -> installed metadata -> __version__ -> serverInfo are one value."""

from __future__ import annotations

import re
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


def test_no_hardcoded_version_literal_in_package() -> None:
    """Every reported version (health, OpenAPI, root info, User-Agent) uses __version__ (#176)."""
    pkg = Path(__file__).resolve().parents[2] / "litvar_link"
    literal = re.compile(r"""["'/]v?\d+\.\d+\.\d+["']""")
    hits = [
        f"{path.relative_to(pkg.parent)}:{n}: {line.strip()}"
        for path in sorted(pkg.rglob("*.py"))
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if literal.search(line) and '__version__ = "0.0.0"' not in line
    ]
    assert hits == [], "use litvar_link.__version__, not a literal:\n" + "\n".join(hits)


def test_reported_versions_match_package() -> None:
    from fastapi.testclient import TestClient

    from litvar_link.app import create_app
    from litvar_link.config import APIConfigModel

    app = create_app()
    assert app.version == __version__
    assert TestClient(app).get("/").json()["version"] == __version__
    assert APIConfigModel().user_agent == f"LitVar-Link/{__version__}"
