"""The size checker flags functions longer than the per-function cap."""

from __future__ import annotations

from pathlib import Path

from scripts.check_file_size import find_oversized_functions


def test_flags_long_function(tmp_path: Path) -> None:
    body = "\n".join(f"    x{i} = {i}" for i in range(70))
    src = f"def big():\n{body}\n"
    f = tmp_path / "m.py"
    f.write_text(src, encoding="utf-8")
    violations = find_oversized_functions(f, limit=60)
    assert any("big" in v for v in violations)


def test_passes_short_function(tmp_path: Path) -> None:
    f = tmp_path / "m.py"
    f.write_text("def small():\n    return 1\n", encoding="utf-8")
    assert find_oversized_functions(f, limit=60) == []
