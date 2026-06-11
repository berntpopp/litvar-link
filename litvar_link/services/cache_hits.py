"""Shared cache-hit detection for the service layer (DRY cluster #2).

Each service method used to inline the same ~12-line "read hits before, call,
read hits after, compare" block. These two helpers replace it.
"""

from __future__ import annotations

from typing import Any


def hits_before(cached_fn: Any) -> int:
    """Return the cached function's current hit count (0 if unavailable)."""
    cache_info = getattr(cached_fn, "cache_info", None)
    if cache_info is None:
        return 0
    return int(cache_info().hits)


def was_cache_hit(cached_fn: Any, *, before: int) -> bool:
    """Return True if the cached function's hit count grew past ``before``."""
    cache_info = getattr(cached_fn, "cache_info", None)
    if cache_info is None:
        return False
    return bool(cache_info().hits > before)
