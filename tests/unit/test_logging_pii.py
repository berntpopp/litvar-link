"""PII-redaction tests for the shared structured-logging helpers (finding M3).

The LitVar2 request surface embeds patient-adjacent identifiers -- rsIDs, HGVS,
gene symbols, free-text queries -- directly in URL path segments, tool params,
error messages, and error context. None of that may reach the log sink. These
tests pin the contract: the shared helpers in ``logging_config`` (and their
route callers) must emit request-tracking metadata only, never the identifier
values themselves.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import httpx
import pytest
import structlog

from litvar_link import logging_config
from litvar_link.api.client import LitVar2Client
from litvar_link.config import APIConfig
from litvar_link.exceptions import LitVarAPIError, ServiceUnavailableError

# A value that could only appear in a log if a caller/variant identifier leaked.
SENTINEL = "rsSENTINEL7f3a"


def _flatten(value: object) -> str:
    """Stringify a captured log value (recursing into dict/list) for matching."""
    if isinstance(value, dict):
        return " ".join(_flatten(v) for v in (*value.keys(), *value.values()))
    if isinstance(value, (list, tuple, set)):
        return " ".join(_flatten(v) for v in value)
    return str(value)


def _assert_no_sentinel(entries: list[dict[str, object]]) -> None:
    """Fail if SENTINEL appears in any captured log entry value."""
    leaks = [
        (entry.get("event"), key, val)
        for entry in entries
        for key, val in entry.items()
        if SENTINEL in _flatten(val)
    ]
    assert not leaks, f"variant/query PII leaked into logs: {leaks}"


class TestVariantLookupDoesNotLeakPII:
    """Drive a real client flow and assert no identifier reaches structlog."""

    @pytest.fixture
    def api_config(self) -> APIConfig:
        return APIConfig(
            base_url="https://test-litvar.api.example.com/",
            timeout=5,
            rate_limit_per_second=10.0,
            burst_size=5,
            max_retries=2,
            retry_delay=0.1,
        )

    @pytest.mark.asyncio
    async def test_failed_variant_lookup_does_not_log_identifier(
        self,
        api_config: APIConfig,
    ) -> None:
        """A failing get_variant_details(SENTINEL) must not log the sentinel.

        The sentinel is carried in the request URL path, in the retry-attempt
        error context, and in the exhausted-retries summary -- all structured
        log fields emitted by the shared helpers. None may contain it.
        """
        transport_error = httpx.ConnectError("connection refused")

        with structlog.testing.capture_logs() as entries:
            logger = structlog.get_logger("litvar_link.test")
            async with LitVar2Client(config=api_config, logger=logger) as client:
                # Force every HTTP attempt to fail at the transport layer so the
                # retry + failure logging paths run with the sentinel in the URL.
                async def _boom(*_args: object, **_kwargs: object) -> httpx.Response:
                    raise transport_error

                client.client.request = _boom  # type: ignore[method-assign]

                with pytest.raises((ServiceUnavailableError, LitVarAPIError)):
                    await client.get_variant_details(SENTINEL)

        # Sanity: the flow must have logged *something*, else the capture is
        # mis-wired and the assertion below would be a false pass.
        assert entries, "expected the failing lookup to emit log records"
        _assert_no_sentinel(entries)


class TestLogApiRequestRedaction:
    """log_api_request must not emit the full URL or a raw error message."""

    def test_success_logs_host_not_full_url(self) -> None:
        logger = MagicMock()

        logging_config.log_api_request(
            logger=logger,
            method="GET",
            url=f"https://api.example.com/variant/get/{SENTINEL}",
            response_time=0.12,
            status_code=200,
        )

        logger.info.assert_called_once()
        kwargs = logger.info.call_args.kwargs
        assert "url" not in kwargs
        assert SENTINEL not in _flatten(kwargs)
        # Operational context (host + timing + status) is preserved.
        assert kwargs["status_code"] == 200
        assert kwargs["response_time_ms"] == 120.0

    def test_error_does_not_log_url_or_raw_error_string(self) -> None:
        logger = MagicMock()

        logging_config.log_api_request(
            logger=logger,
            method="GET",
            url=f"https://api.example.com/variant/get/{SENTINEL}",
            response_time=0.2,
            status_code=0,
            error=f"Request timeout: https://api.example.com/variant/get/{SENTINEL}",
        )

        logger.error.assert_called_once()
        kwargs = logger.error.call_args.kwargs
        assert "url" not in kwargs
        assert SENTINEL not in _flatten(kwargs)


class TestLogMcpToolCallRedaction:
    """log_mcp_tool_call must not emit raw param values."""

    def test_params_values_are_not_logged(self) -> None:
        logger = MagicMock()

        logging_config.log_mcp_tool_call(
            logger=logger,
            tool_name="search_genetic_variants",
            params={"query": SENTINEL, "limit": 10},
            duration=0.5,
            success=True,
        )

        logger.info.assert_called_once()
        kwargs = logger.info.call_args.kwargs
        assert SENTINEL not in _flatten(kwargs)
        assert kwargs["tool_name"] == "search_genetic_variants"
        # Key names are safe metadata; values must be gone.
        assert "query" in _flatten(kwargs.get("param_keys", []))


class TestLogErrorWithContextRedaction:
    """log_error_with_context must not emit error_message or raw context."""

    def test_error_message_and_context_values_are_redacted(self) -> None:
        logger = MagicMock()
        error = ValueError(f"No LitVar2 variant found for {SENTINEL!r}")

        logging_config.log_error_with_context(
            logger=logger,
            error=error,
            operation="get_variant_summary",
            context={"variant_id": SENTINEL, "attempt": 2},
        )

        logger.error.assert_called_once()
        kwargs = logger.error.call_args.kwargs
        assert kwargs["operation"] == "get_variant_summary"
        assert kwargs["error_type"] == "ValueError"
        assert "error_message" not in kwargs
        assert "context" not in kwargs
        assert SENTINEL not in _flatten(kwargs)
