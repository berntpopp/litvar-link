"""Centralized caching utilities and decorators."""

from __future__ import annotations

import functools
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, TypeVar, cast

from async_lru import alru_cache

from litvar_link.logging_config import log_cache_operation

if TYPE_CHECKING:
    from collections.abc import Awaitable, Coroutine

    from structlog.typing import FilteringBoundLogger

# Type variables for generic function signatures
P = TypeVar("P")
R = TypeVar("R")


def _build_cache_key(
    func_name: str,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    key_pattern: str | None,
) -> str:
    """Build a logging cache key from the call signature.

    Uses ``key_pattern`` when provided, otherwise the function name, then
    appends positional args and sorted keyword args.
    """
    prefix = key_pattern or func_name
    key = f"{prefix}:{':'.join(str(arg) for arg in args)}"
    if kwargs:
        key_parts = [f"{k}={v}" for k, v in sorted(kwargs.items())]
        key += f":{':'.join(key_parts)}"
    return key


class CacheManager:
    """Centralized cache management with statistics tracking."""

    def __init__(self, logger: FilteringBoundLogger | None = None) -> None:
        """Initialize cache manager.

        Args:
            logger: Optional logger for cache operations
        """
        self.logger = logger
        self._cache_stats = {"hits": 0, "misses": 0}
        self._cached_functions: list[Any] = []

    @property
    def cache_stats(self) -> dict[str, Any]:
        """Get comprehensive cache statistics."""
        total_requests = self._cache_stats["hits"] + self._cache_stats["misses"]
        hit_rate = self._cache_stats["hits"] / total_requests if total_requests > 0 else 0.0

        return {
            "hits": self._cache_stats["hits"],
            "misses": self._cache_stats["misses"],
            "hit_rate": hit_rate * 100.0,  # Convert to percentage
            "total_requests": total_requests,
            "cached_functions": len(self._cached_functions),
        }

    def _log_cache_hit(self, key: str) -> None:
        """Log cache hit and update statistics."""
        self._cache_stats["hits"] += 1
        if self.logger:
            log_cache_operation(self.logger, "hit", key, hit=True)

    def _log_cache_miss(self, key: str) -> None:
        """Log cache miss and update statistics."""
        self._cache_stats["misses"] += 1
        if self.logger:
            log_cache_operation(self.logger, "miss", key, hit=False)

    def cached(
        self,
        maxsize: int = 256,
        ttl: int = 3600,
        key_pattern: str | None = None,
    ) -> Callable[[Callable[..., Awaitable[R]]], Callable[..., Awaitable[R]]]:
        """Advanced caching decorator with statistics tracking.

        Wraps an async function with :func:`async_lru.alru_cache` plus hit/miss
        statistics and structured logging of each cache operation.

        Args:
            maxsize: Maximum number of cached items (default: 256).
            ttl: Time-to-live in seconds (default: 3600).
            key_pattern: Optional prefix for generated cache keys.

        Returns:
            Decorator that adds caching to an async function.
        """

        def decorator(func: Callable[..., Awaitable[R]]) -> Callable[..., Awaitable[R]]:
            cached_func = alru_cache(maxsize=maxsize, ttl=ttl)(
                cast("Callable[..., Coroutine[Any, Any, R]]", func),
            )
            self._cached_functions.append(cached_func)

            @functools.wraps(func)
            async def wrapper(*args: Any, **kwargs: Any) -> R:
                cache_key = _build_cache_key(func.__name__, args, kwargs, key_pattern)
                initial_hits = cached_func.cache_info().hits
                start_time = time.time()

                result = await cached_func(*args, **kwargs)

                cache_info_after = cached_func.cache_info()
                was_cache_hit = cache_info_after.hits > initial_hits
                if was_cache_hit:
                    self._log_cache_hit(cache_key)
                else:
                    self._log_cache_miss(cache_key)

                if self.logger:
                    self.logger.debug(
                        "Cache operation completed",
                        cache_key=cache_key,
                        hit=was_cache_hit,
                        execution_time_ms=(time.time() - start_time) * 1000,
                        cache_size=cache_info_after.currsize,
                        max_size=maxsize,
                    )

                return result

            # Store cache info access for management
            wrapper.cache_info = cached_func.cache_info  # type: ignore
            wrapper.cache_clear = cached_func.cache_clear  # type: ignore

            return wrapper

        return decorator

    def clear_all_caches(self, pattern: str | None = None) -> dict[str, int]:
        """Clear all managed caches.

        Args:
            pattern: Optional pattern to match (currently unused, clears all)

        Returns:
            Dictionary with cleared cache statistics
        """
        cleared_count = 0
        cleared_functions = 0

        for cached_func in self._cached_functions:
            if hasattr(cached_func, "cache_info") and hasattr(
                cached_func,
                "cache_clear",
            ):
                info_before = cached_func.cache_info()
                cached_func.cache_clear()
                cleared_count += info_before.currsize
                cleared_functions += 1

        if self.logger:
            log_cache_operation(
                self.logger,
                "clear_all",
                pattern or "all",
                size=cleared_count,
            )

        return {
            "cleared_count": cleared_count,
            "cleared_functions": cleared_functions,
        }

    def get_cache_info(self) -> dict[str, Any]:
        """Get detailed information about all cached functions.

        Returns:
            Dictionary with cache information for each function
        """
        cache_info = {}

        for i, cached_func in enumerate(self._cached_functions):
            if hasattr(cached_func, "cache_info"):
                info = cached_func.cache_info()
                func_name = getattr(cached_func, "__name__", f"function_{i}")
                cache_info[func_name] = {
                    "hits": info.hits,
                    "misses": info.misses,
                    "current_size": info.currsize,
                    "max_size": info.maxsize,
                    "hit_rate": (
                        (info.hits / (info.hits + info.misses) * 100.0)
                        if (info.hits + info.misses) > 0
                        else 0.0
                    ),
                }

        return cache_info


def create_service_cache_decorator(
    logger: FilteringBoundLogger | None = None,
) -> CacheManager:
    """Create a cache manager for services.

    This provides a convenient way to create a cache manager with
    sensible defaults for service layer caching.

    Args:
        logger: Optional logger for cache operations

    Returns:
        Configured CacheManager instance

    Example:
        ```python
        from litvar_link.utils.caching import create_service_cache_decorator

        cache = create_service_cache_decorator(logger)

        class VariantService:
            @cache.cached(maxsize=500, ttl=7200, key_pattern="variant_details")
            async def get_variant_details(self, variant_id: str) -> dict:
                return await self.client.get_variant_details(variant_id)
        ```
    """
    return CacheManager(logger)
