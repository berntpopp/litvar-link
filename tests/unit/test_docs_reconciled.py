"""Docs describe the realized P3 module tree, not the P1 'target'."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
ARCH = ROOT / "docs" / "architecture.md"
AGENTS = ROOT / "AGENTS.md"

REALIZED_MODULES = [
    "litvar_link/validation.py",
    "litvar_link/api/rate_limiter.py",
    "litvar_link/api/parsing.py",
    "litvar_link/api/retry.py",
    "litvar_link/api/error_handlers.py",
    "litvar_link/services/cache_hits.py",
    "litvar_link/mcp/facade.py",
]


def test_architecture_mentions_realized_modules() -> None:
    text = ARCH.read_text(encoding="utf-8")
    for module in REALIZED_MODULES:
        assert module in text, f"architecture.md missing {module}"


def test_architecture_drops_target_caveat() -> None:
    text = ARCH.read_text(encoding="utf-8").lower()
    # The P1 doc labelled the layout as a future target; P3 makes it present.
    assert "target layout (realized in p3)" not in text
    assert "(target, post-p3)" not in text


def test_agents_documents_function_size_policy() -> None:
    text = AGENTS.read_text(encoding="utf-8")
    assert "60" in text  # per-function line cap
    assert "C901" in text and "PLR0915" in text
