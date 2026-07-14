"""The README '## Tools' table must match the server's registered tools exactly.

GeneFoundry README Standard v1, Rule 6: the tool table is machine-verified, not
hand-maintained. Adding, removing, or renaming a tool without updating the README
fails here — the table cannot drift.

The live tool list comes from the same ``facade`` fixture ``test_tool_names.py``
uses (``create_litvar_mcp`` in ``tests/conftest.py``); it is never hardcoded.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

README = Path(__file__).parent.parent.parent / "README.md"

# A row in the tools table: | `tool_name` | Purpose. |
_ROW_RE = re.compile(r"^\|\s*`([a-z0-9_]+)`\s*\|")


def _readme_tool_names() -> set[str]:
    """Parse the tool names out of the README's '## Tools' section."""
    lines = README.read_text(encoding="utf-8").splitlines()

    try:
        start = lines.index("## Tools")
    except ValueError:  # pragma: no cover - guarded by test_readme_has_tools_section
        return set()

    names: set[str] = set()
    for line in lines[start + 1 :]:
        if line.startswith("## "):  # next section ends the table
            break
        match = _ROW_RE.match(line)
        if match:
            names.add(match.group(1))
    return names


def test_readme_has_a_tools_section() -> None:
    assert "## Tools" in README.read_text(encoding="utf-8"), "README lost its '## Tools' section"


async def test_readme_tool_table_matches_registered_tools(facade: Any) -> None:
    registered = {tool.name for tool in await facade.list_tools()}
    assert registered, "no tools registered on the facade"

    documented = _readme_tool_names()

    missing = registered - documented
    extra = documented - registered
    assert not missing, f"tools registered but absent from the README table: {sorted(missing)}"
    assert not extra, f"tools in the README table but not registered: {sorted(extra)}"
    assert documented == registered
