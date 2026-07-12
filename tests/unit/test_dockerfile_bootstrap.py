"""Reproducible builder bootstrap: pin uv by digest, no floating pip/uv upgrade (F-19).

A ``pip install --upgrade pip uv`` at build time pulls whatever PyPI serves that
day — a supply-chain / non-reproducibility hazard. The builder must instead COPY
the uv binary from a digest-pinned image (the same anchor the whole fleet shares).
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # tests/unit/<file> -> repo root

_UV_COPY_PIN = (
    "ghcr.io/astral-sh/uv:0.8.7@sha256:"
    "1e26f9a868360eeb32500a35e05787ffff3402f01a8dc8168ef6aee44aef0aab"
)


def test_dockerfile_pins_uv_and_has_no_floating_pip_upgrade() -> None:
    text = (ROOT / "docker" / "Dockerfile").read_text(encoding="utf-8")
    assert "pip install --upgrade" not in text, "floating pip/uv upgrade must be removed"
    assert _UV_COPY_PIN in text, "uv must be COPYed from the digest-pinned image"
