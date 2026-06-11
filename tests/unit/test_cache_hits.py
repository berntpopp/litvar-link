"""Unit tests for the shared cache-hit detection helper (DRY cluster #2)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from litvar_link.services.cache_hits import hits_before, was_cache_hit


class _Cached:
    """Minimal stand-in exposing the alru_cache cache_info() surface."""

    def __init__(self, hits: int) -> None:
        self._hits = hits

    def cache_info(self) -> Any:
        return SimpleNamespace(hits=self._hits)


def test_hits_before_reads_current_hits() -> None:
    assert hits_before(_Cached(7)) == 7


def test_hits_before_none_when_no_cache_info() -> None:
    assert hits_before(object()) == 0


def test_was_cache_hit_true_when_hits_increased() -> None:
    assert was_cache_hit(_Cached(5), before=4) is True


def test_was_cache_hit_false_when_unchanged() -> None:
    assert was_cache_hit(_Cached(4), before=4) is False


def test_was_cache_hit_false_without_cache_info() -> None:
    assert was_cache_hit(object(), before=0) is False
