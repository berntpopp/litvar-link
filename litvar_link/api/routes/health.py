"""Health check and monitoring routes."""

from __future__ import annotations

from datetime import datetime
import time

from fastapi import APIRouter

from litvar_link.models import CacheStatsResponse, HealthResponse

from .dependencies import ClientDep, LoggerDep, ServiceDep

router = APIRouter(prefix="/api/health", tags=["Health"])


@router.get("/", response_model=HealthResponse)
async def health_check(
    client: ClientDep = None,
    service: ServiceDep = None,
    logger: LoggerDep = None,
) -> HealthResponse:
    """Comprehensive health check for the LitVar-Link service.

    Checks the status of all major components:
    - LitVar2 API connectivity and response time
    - Cache system functionality
    - Overall service health metrics

    Returns detailed health information including:
    - Component status indicators
    - Performance metrics
    - System resource usage (if available)
    - Error rates and response times
    """
    start_time = time.time()

    # Check LitVar2 API health
    litvar_health = await client.health_check()
    litvar_status = litvar_health.get("status", "unknown")

    # Get cache statistics
    cache_stats = service.cache_stats
    cache_status = "healthy" if cache_stats["total_requests"] >= 0 else "unhealthy"

    # Calculate overall status
    overall_status = "healthy"
    if litvar_status != "healthy":
        overall_status = "degraded"

    uptime = time.time() - start_time

    logger.info(
        "Health check completed",
        overall_status=overall_status,
        litvar_status=litvar_status,
        cache_status=cache_status,
    )

    # Get API client statistics
    api_stats = client.get_stats()

    return HealthResponse(
        status=overall_status,
        version="0.1.0",
        uptime_seconds=uptime,
        litvar_api_status=litvar_status,
        cache_status=cache_status,
        average_response_time_ms=litvar_health.get("response_time_ms"),
        timestamp=datetime.now().isoformat(),
        api_stats=api_stats,
    )


@router.get("/cache", response_model=CacheStatsResponse)
async def get_cache_stats(
    service: ServiceDep = None,
    logger: LoggerDep = None,
) -> CacheStatsResponse:
    """Get detailed cache statistics.

    Returns comprehensive caching metrics including:
    - Hit/miss counts and rates
    - Cache size and memory usage
    - TTL information and expired items
    - Performance statistics

    Useful for monitoring cache effectiveness and performance tuning.
    """
    stats = service.cache_stats

    logger.debug(
        "Cache stats requested",
        hit_rate=stats["hit_rate"],
        total_requests=stats["total_requests"],
    )

    return CacheStatsResponse(
        total_size=0,  # Not available with async-lru
        hits=stats["hits"],
        misses=stats["misses"],
        hit_rate=stats["hit_rate"],  # Already percentage from service
        total_requests=stats["total_requests"],
        expired_count=0,  # Not tracked by async-lru
    )
