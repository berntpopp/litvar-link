"""Unit tests for TokenBucketRateLimiter (moved out of client.py)."""

from __future__ import annotations

import pytest

from litvar_link.api.rate_limiter import TokenBucketRateLimiter


@pytest.mark.asyncio
async def test_acquire_within_burst_no_wait() -> None:
    limiter = TokenBucketRateLimiter(rate=2.0, burst=5)
    wait = await limiter.acquire()
    assert wait == 0.0


@pytest.mark.asyncio
async def test_acquire_exhausts_burst_then_waits() -> None:
    limiter = TokenBucketRateLimiter(rate=2.0, burst=1)
    assert await limiter.acquire() == 0.0
    wait = await limiter.acquire()
    assert wait > 0.0


def test_current_tokens_property() -> None:
    limiter = TokenBucketRateLimiter(rate=2.0, burst=5)
    assert limiter.current_tokens <= 5.0


def test_reexported_from_client() -> None:
    # Existing imports `from litvar_link.api.client import TokenBucketRateLimiter`
    # must keep working.
    from litvar_link.api.client import TokenBucketRateLimiter as ReExported

    assert ReExported is TokenBucketRateLimiter
