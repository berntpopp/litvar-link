"""Unit tests for retry backoff math and HTTP status classification."""

from __future__ import annotations

import pytest

from litvar_link.api.retry import backoff_delay, raise_for_status_code
from litvar_link.exceptions import (
    LitVarAPIError,
    RateLimitError,
    ServiceUnavailableError,
)


class TestBackoffDelay:
    @pytest.mark.parametrize(
        ("attempt", "expected"),
        [(0, 1.0), (1, 2.0), (2, 4.0)],
    )
    def test_exponential(self, attempt: int, expected: float) -> None:
        assert backoff_delay(base=1.0, attempt=attempt) == expected


class TestRaiseForStatusCode:
    def test_429_raises_rate_limit(self) -> None:
        with pytest.raises(RateLimitError) as exc:
            raise_for_status_code(429, url="http://x", text="", retry_after=30.0)
        assert exc.value.retry_after == 30.0

    def test_500_raises_service_unavailable(self) -> None:
        with pytest.raises(ServiceUnavailableError):
            raise_for_status_code(503, url="http://x", text="")

    def test_400_raises_api_error_with_status(self) -> None:
        with pytest.raises(LitVarAPIError) as exc:
            raise_for_status_code(404, url="http://x", text="missing")
        assert exc.value.status_code == 404

    def test_2xx_does_not_raise(self) -> None:
        assert raise_for_status_code(200, url="http://x", text="") is None
