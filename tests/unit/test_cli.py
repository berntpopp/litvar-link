"""CLI parity: command/flag surface and exit codes survive argparse -> typer.

The scripting contract (command names, per-command flags, serve sub-commands,
exit codes) is the thing that must NOT silently change across the argparse ->
typer migration. Exact ``--help`` wording differs between the two help
renderers, so this snapshot pins the STABLE contract, not byte-for-byte text.

These tests drive the CLI through ``python -m litvar_link.cli`` so they exercise
the real console-script invocation path and remain valid for both the argparse
(pre-3.6.2) and typer (post-3.6.2) implementations.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

SNAPSHOT = Path(__file__).parent.parent / "fixtures" / "cli_help_snapshot.json"

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

# The scripting contract that must not silently change.
EXPECTED = {
    "commands": {"test", "search", "rsid", "gene", "serve"},
    "search_flags": {"--limit"},
    "gene_flags": {"--limit"},
    "serve_subcommands": {"http", "unified", "mcp"},
    "serve_http_flags": {"--host", "--port", "--reload"},
}


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    """Invoke the CLI module the same way the console script does.

    Force a wide, un-styled terminal (``COLUMNS=200``, ``NO_COLOR``, ``TERM=dumb``)
    and strip ANSI escapes from stdout. typer's rich help renderer otherwise
    wraps and ANSI-fragments long option names under a narrow non-TTY terminal
    (CI defaults to 80 columns), which made the ``--limit`` / ``--reload``
    substring checks flaky. The scripting contract is width-independent, so the
    flag text must be asserted against the de-styled, unwrapped output.
    """
    env = {**os.environ, "COLUMNS": "200", "NO_COLOR": "1", "TERM": "dumb"}
    result = subprocess.run(  # noqa: S603 - fixed argv (sys.executable + literal module), no shell, no untrusted input
        [sys.executable, "-m", "litvar_link.cli", *args],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    result.stdout = _ANSI_RE.sub("", result.stdout)
    return result


def test_root_help_exit_zero_and_lists_commands() -> None:
    result = _run_cli("--help")
    assert result.returncode == 0
    for cmd in EXPECTED["commands"]:
        assert cmd in result.stdout


def test_search_help_has_limit_flag() -> None:
    result = _run_cli("search", "--help")
    assert result.returncode == 0
    assert "--limit" in result.stdout


def test_gene_help_has_limit_flag() -> None:
    result = _run_cli("gene", "--help")
    assert result.returncode == 0
    assert "--limit" in result.stdout


def test_serve_subcommands_present() -> None:
    result = _run_cli("serve", "--help")
    assert result.returncode == 0
    for sub in EXPECTED["serve_subcommands"]:
        assert sub in result.stdout


def test_serve_http_flags_present() -> None:
    result = _run_cli("serve", "http", "--help")
    assert result.returncode == 0
    for flag in EXPECTED["serve_http_flags"]:
        assert flag in result.stdout


def test_unknown_command_exits_nonzero() -> None:
    result = _run_cli("does-not-exist")
    assert result.returncode != 0


def test_snapshot_recorded_and_matches_contract() -> None:
    if not SNAPSHOT.exists():
        SNAPSHOT.write_text(
            json.dumps(EXPECTED, indent=2, default=list),
            encoding="utf-8",
        )
    recorded = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    assert set(recorded["commands"]) == EXPECTED["commands"]
    assert set(recorded["search_flags"]) == EXPECTED["search_flags"]
    assert set(recorded["gene_flags"]) == EXPECTED["gene_flags"]
    assert set(recorded["serve_subcommands"]) == EXPECTED["serve_subcommands"]
    assert set(recorded["serve_http_flags"]) == EXPECTED["serve_http_flags"]
