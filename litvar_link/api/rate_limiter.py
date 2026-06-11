"""Token-bucket rate limiter for LitVar2 API requests."""

from __future__ import annotations

import asyncio
import time


class TokenBucketRateLimiter:
    """Token bucket rate limiter for API requests."""

    # Constants for rate calculation
    _RATE_WINDOW_SECONDS = 10.0
    _MIN_REQUESTS_FOR_RATE = 2

    def __init__(self, rate: float, burst: int = 1) -> None:
        """Initialize rate limiter.

        Args:
            rate: Requests per second
            burst: Maximum burst size
        """
        self.rate = rate
        self.burst = float(burst)
        self.tokens = float(burst)
        self.last_update = time.time()
        self._lock = asyncio.Lock()
        self.request_times: list[float] = []

    async def acquire(self) -> float:
        """Acquire a token, waiting if necessary.

        Returns:
            Wait time in seconds (0 if no wait required)
        """
        async with self._lock:
            now = time.time()
            # Add tokens based on elapsed time
            elapsed = now - self.last_update
            self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
            self.last_update = now

            if self.tokens >= 1:
                self.tokens -= 1
                # Track request time for rate calculation
                self.request_times.append(now)
                # Keep only recent requests
                self.request_times = [
                    t for t in self.request_times if now - t <= self._RATE_WINDOW_SECONDS
                ]
                return 0.0
            # Calculate wait time for next token
            return (1 - self.tokens) / self.rate

    @property
    def current_tokens(self) -> float:
        """Get current number of available tokens without updating state."""
        now = time.time()
        elapsed = now - self.last_update
        return min(self.burst, self.tokens + elapsed * self.rate)

    def current_rate(self) -> float:
        """Get current rate based on recent request times.

        Returns:
            Current estimated rate in requests per second
        """
        now = time.time()
        # Clean up old request times
        recent_requests = [t for t in self.request_times if now - t <= self._RATE_WINDOW_SECONDS]

        if len(recent_requests) < self._MIN_REQUESTS_FOR_RATE:
            return 0.0

        # Calculate rate based on requests over time window
        time_window = now - recent_requests[0]
        if time_window <= 0:
            return 0.0

        return len(recent_requests) / time_window
