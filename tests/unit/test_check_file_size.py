"""The size checker flags functions longer than the per-function cap."""

from __future__ import annotations

from pathlib import Path

from scripts.check_file_size import _check_file, find_oversized_functions


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


def test_flags_async_function(tmp_path: Path) -> None:
    body = "\n".join(f"    x{i} = {i}" for i in range(70))
    src = f"async def big():\n{body}\n"
    f = tmp_path / "m.py"
    f.write_text(src, encoding="utf-8")
    assert any("big" in v for v in find_oversized_functions(f, limit=60))


def test_check_file_flags_oversized_file(tmp_path: Path) -> None:
    f = tmp_path / "m.py"
    f.write_text("\n".join(f"x = {i}" for i in range(50)), encoding="utf-8")
    msg = _check_file(f, limit=10, file_allowlist={})
    assert msg is not None and "limit 10" in msg


def test_check_file_respects_file_ceiling(tmp_path: Path) -> None:
    f = tmp_path / "m.py"
    f.write_text("\n".join(f"x = {i}" for i in range(50)), encoding="utf-8")
    rel = f.as_posix()
    # Within the grandfathered ceiling -> no message.
    assert _check_file(f, limit=10, file_allowlist={rel: 100}) is None
    # Grown past the ceiling -> message.
    grew = _check_file(f, limit=10, file_allowlist={rel: 5})
    assert grew is not None and "grandfathered ceiling" in grew
