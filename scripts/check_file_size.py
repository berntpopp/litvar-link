"""Fail on Python source exceeding the per-file or per-function line budget.

Rationale: large modules and functions concentrate complexity and slow
LLM-assisted refactors. See AGENTS.md "File & Function Size Discipline".

The default budgets are 600 lines per file and 60 lines per function. Existing
oversized files/functions are grandfathered via `.loc-allowlist`:

    path[:ceiling]               # grandfathered file
    path::function[:ceiling]     # grandfathered function

Allowlisted entries must not grow beyond their listed ceiling.

Usage:
    python scripts/check_file_size.py            # check all configured paths
    python scripts/check_file_size.py path/...   # check specific paths
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

DEFAULT_LIMIT = 600
DEFAULT_FUNCTION_LIMIT = 60
DEFAULT_TARGETS = (
    Path("litvar_link"),
    Path("server.py"),
    Path("mcp_server.py"),
)
ALLOWLIST_PATH = Path(".loc-allowlist")


def _load_allowlist() -> tuple[dict[str, int], dict[str, int]]:
    """Return ``(file_ceilings, function_ceilings)`` from ``.loc-allowlist``.

    Each non-comment, non-empty line is one of:

    - ``path[:ceiling]`` — a grandfathered file. Omitting the ceiling defers
      to the current file length at first run (recorded as ``-1``).
    - ``path::function[:ceiling]`` — a grandfathered function. Omitting the
      ceiling treats any size as allowed (recorded as ``-1``).

    Function entries are keyed ``"path::function"`` so the per-function cap
    can look them up directly.
    """
    if not ALLOWLIST_PATH.exists():
        return {}, {}
    file_entries: dict[str, int] = {}
    func_entries: dict[str, int] = {}
    for raw in ALLOWLIST_PATH.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if "::" in line:
            target, _, rest = line.partition("::")
            if ":" in rest:
                fname, ceiling = rest.split(":", 1)
                func_entries[f"{target.strip()}::{fname.strip()}"] = int(ceiling.strip())
            else:
                func_entries[f"{target.strip()}::{rest.strip()}"] = -1
        elif ":" in line:
            path, ceiling = line.split(":", 1)
            file_entries[path.strip()] = int(ceiling.strip())
        else:
            file_entries[line] = -1
    return file_entries, func_entries


def find_oversized_functions(
    path: Path,
    *,
    limit: int = DEFAULT_FUNCTION_LIMIT,
) -> list[str]:
    """Return messages for functions whose body spans more than ``limit`` lines.

    Span = ``end_lineno - lineno + 1`` (decorators excluded by ``ast``). Both
    sync and async functions, including nested ones, are checked.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return []
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            start = node.lineno
            end = getattr(node, "end_lineno", start) or start
            span = end - start + 1
            if span > limit:
                violations.append(
                    f"  {path.as_posix()}::{node.name} ({path.as_posix()}:{start}): "
                    f"{span} lines (limit {limit}). Decompose."
                )
    return violations


def _iter_python_files(targets: list[Path]) -> list[Path]:
    files: list[Path] = []
    for target in targets:
        if not target.exists():
            continue
        if target.is_file() and target.suffix == ".py":
            files.append(target)
            continue
        files.extend(sorted(target.rglob("*.py")))
    return files


def _line_count(path: Path) -> int:
    with path.open("rb") as handle:
        return sum(1 for _ in handle)


class _Findings:
    """Accumulated budget violations across the scanned files."""

    def __init__(self) -> None:
        self.files: list[str] = []
        self.functions: list[str] = []
        self.grew: list[str] = []

    @property
    def clean(self) -> bool:
        return not (self.files or self.functions or self.grew)


def _check_functions(
    path: Path,
    limit: int,
    func_allowlist: dict[str, int],
) -> list[str]:
    """Return non-allowlisted per-function violations for ``path``."""
    out: list[str] = []
    for msg in find_oversized_functions(path, limit=limit):
        key = msg.strip().split(" ", 1)[0]  # "path::function"
        if key not in func_allowlist:
            out.append(msg)
    return out


def _check_file(path: Path, limit: int, file_allowlist: dict[str, int]) -> str | None:
    """Return a per-file violation message for ``path``, or None if within budget."""
    rel = path.as_posix()
    loc = _line_count(path)
    if rel in file_allowlist:
        ceiling = file_allowlist[rel]
        if ceiling > 0 and loc > ceiling:
            return (
                f"  {rel}: {loc} lines (grandfathered ceiling {ceiling}). "
                f"Decompose or lower the entry in .loc-allowlist."
            )
        return None
    if loc > limit:
        return (
            f"  {rel}: {loc} lines (limit {limit}). "
            f"Split into smaller modules. See AGENTS.md 'File Size Discipline'."
        )
    return None


def _collect(targets: list[Path], file_limit: int, function_limit: int) -> _Findings:
    """Scan ``targets`` and accumulate file/function budget findings."""
    file_allowlist, func_allowlist = _load_allowlist()
    findings = _Findings()
    for path in _iter_python_files(targets):
        findings.functions.extend(_check_functions(path, function_limit, func_allowlist))
        message = _check_file(path, file_limit, file_allowlist)
        if message is None:
            continue
        if "grandfathered ceiling" in message:
            findings.grew.append(message)
        else:
            findings.files.append(message)
    return findings


def _report(findings: _Findings) -> None:
    """Write a human-readable report of ``findings`` to stderr."""
    if findings.files:
        sys.stderr.write("\nFiles exceeding the per-file line budget:\n")
        sys.stderr.write("\n".join(findings.files) + "\n")
    if findings.functions:
        sys.stderr.write("\nFunctions exceeding the per-function line budget:\n")
        sys.stderr.write("\n".join(findings.functions) + "\n")
    if findings.grew:
        sys.stderr.write("\nGrandfathered files that have grown past their ceiling:\n")
        sys.stderr.write("\n".join(findings.grew) + "\n")
    sys.stderr.write(
        "\nAdd new files/functions to .loc-allowlist with an explicit ceiling only "
        "as a temporary exception with a tracked decomposition plan.\n"
    )


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", type=Path)
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=f"max lines per file for unallowlisted modules (default: {DEFAULT_LIMIT})",
    )
    parser.add_argument(
        "--function-limit",
        type=int,
        default=DEFAULT_FUNCTION_LIMIT,
        help=(
            "max lines per function for unallowlisted functions "
            f"(default: {DEFAULT_FUNCTION_LIMIT})"
        ),
    )
    args = parser.parse_args(argv)

    targets = args.paths or list(DEFAULT_TARGETS)
    findings = _collect(targets, args.limit, args.function_limit)
    if findings.clean:
        return 0
    _report(findings)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
