from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


def test_repo_slug_uses_origin_in_an_isolated_worktree(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    script = Path(__file__).parents[2] / "scripts" / "check_readme.py"
    spec = importlib.util.spec_from_file_location("check_readme", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ROOT", tmp_path / "fleet-release")

    class Result:
        stdout = "https://github.com/berntpopp/litvar-link.git\n"

    monkeypatch.setattr(module.subprocess, "run", lambda *args, **kwargs: Result())
    assert module.repo_slug() == "litvar-link"
