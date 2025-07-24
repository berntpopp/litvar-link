"""Centralized caching utilities and decorators."""

from __future__ import annotations

import functools
import time
from typing import TYPE_CHECKING, Any, Awaitable, Callable, TypeVar

from async_lru import alru_cache

from litvar_link.logging_config import log_cache_operation

if TYPE_CHECKING:
    from structlog.typing import FilteringBoundLogger

# Type variables for generic function signatures
P = TypeVar("P")
R = TypeVar("R")


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
        hit_rate = (
            self._cache_stats["hits"] / total_requests if total_requests > 0 else 0.0
        )

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

        This decorator provides unified caching functionality with:
        - Configurable cache size and TTL
        - Automatic cache statistics tracking
        - Centralized logging of cache operations
        - Support for custom cache key patterns

        Args:
            maxsize: Maximum number of cached items (default: 256)
            ttl: Time-to-live in seconds (default: 3600 = 1 hour)
            key_pattern: Optional pattern for generating cache keys

        Returns:
            Decorated function with caching capabilities

        Example:
            ```python
            cache_manager = CacheManager(logger)

            @cache_manager.cached(maxsize=500, ttl=7200, key_pattern="variant_details")
            async def get_variant_details(variant_id: str) -> dict:
                return await client.get_variant_details(variant_id)
            ```
        """

        def decorator(func: Callable[..., Awaitable[R]]) -> Callable[..., Awaitable[R]]:
            # Create the cached version using alru_cache
            cached_func = alru_cache(maxsize=maxsize, ttl=ttl)(func)
            self._cached_functions.append(cached_func)

            @functools.wraps(func)
            async def wrapper(*args: Any, **kwargs: Any) -> R:
                # Generate cache key for logging
                if key_pattern:
                    cache_key = f"{key_pattern}:{':'.join(str(arg) for arg in args)}"
                    if kwargs:
                        key_parts = [f"{k}={v}" for k, v in sorted(kwargs.items())]
                        cache_key += f":{':'.join(key_parts)}"
                else:
                    cache_key = f"{func.__name__}:{':'.join(str(arg) for arg in args)}"

                # Check cache hit/miss by comparing cache info before and after
                cache_info_before = cached_func.cache_info()
                initial_hits = cache_info_before.hits

                start_time = time.time()

                # Execute cached function
                result = await cached_func(*args, **kwargs)

                # Determine if cache was hit
                cache_info_after = cached_func.cache_info()
                was_cache_hit = cache_info_after.hits > initial_hits

                # Log cache operation
                if was_cache_hit:
                    self._log_cache_hit(cache_key)
                else:
                    self._log_cache_miss(cache_key)

                # Log performance metrics
                execution_time = (time.time() - start_time) * 1000
                if self.logger:
                    self.logger.debug(
                        "Cache operation completed",
                        cache_key=cache_key,
                        hit=was_cache_hit,
                        execution_time_ms=execution_time,
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
                cached_func, "cache_clear"
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
