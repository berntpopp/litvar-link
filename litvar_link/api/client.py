"""LitVar2 API client with rate limiting and error handling."""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any, Self, cast
from urllib.parse import quote, urljoin, urlsplit

import httpx

from litvar_link.api.parsing import extract_list, parse_ndjson, parse_response_body
from litvar_link.api.rate_limiter import TokenBucketRateLimiter
from litvar_link.api.retry import (
    HTTP_TOO_MANY_REQUESTS,
    backoff_delay,
    raise_for_status_code,
)
from litvar_link.api.url_guard import (
    DisallowedURLError,
    ResponseTooLargeError,
    build_allowed_origins,
    make_response_cap,
    make_url_guard,
)
from litvar_link.exceptions import (
    LitVarAPIError,
    RateLimitError,
    ServiceUnavailableError,
    UpstreamPolicyError,
)
from litvar_link.logging_config import log_api_request, log_error_with_context
from litvar_link.validation import (
    validate_gene_name,
    validate_limit,
    validate_query,
    validate_rsid,
)

if TYPE_CHECKING:
    import types

    from structlog.typing import FilteringBoundLogger

    from litvar_link.config import APIConfig


def _format_endpoint(template: str, **segments: str) -> str:
    """Substitute path segments into an endpoint template, percent-encoding each.

    LitVar2 canonical ids look like ``litvar@rs113993960##``; the ``@`` and the
    trailing ``##`` MUST be percent-encoded, because an unencoded ``#`` is parsed
    as a URL fragment delimiter -- the path is then silently truncated and the
    server 400s ("Variant not found"). Every dynamic segment is quoted with
    ``safe=""`` so reserved characters never leak into the path.
    """
    encoded = {key: quote(str(value), safe="") for key, value in segments.items()}
    return template.format(**encoded)


class LitVar2Client:
    """HTTP client for LitVar2 API with rate limiting and error handling."""

    # Keep only the most recent response times for statistics.
    _RESPONSE_TIME_WINDOW = 100

    def __init__(
        self,
        config: APIConfig,
        logger: FilteringBoundLogger | None = None,
    ) -> None:
        """Initialize LitVar2 client.

        Args:
            config: API configuration
            logger: Optional logger instance
        """
        self.config = config
        self.logger = logger

        # Initialize statistics tracking
        self.total_requests = 0
        self.successful_requests = 0
        self.response_times: list[float] = []

        # Initialize rate limiter
        self.rate_limiter = TokenBucketRateLimiter(
            rate=config.rate_limit_per_second,
            burst=config.burst_size,
        )

        # Initialize HTTP client. Redirects stay enabled but every hop is
        # validated by a request event-hook against an allowlist DERIVED from the
        # configured base URL host, and the response body is capped fail-closed.
        allowed_origins = build_allowed_origins(config.base_url)
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(config.timeout),
            headers={
                "User-Agent": config.user_agent,
                "Accept": "application/json",
            },
            follow_redirects=True,
            max_redirects=5,
            event_hooks={
                "request": [make_url_guard(allowed_origins)],
                "response": [make_response_cap(config.max_response_bytes)],
            },
        )

    async def close(self) -> None:
        """Close HTTP client."""
        await self.client.aclose()

    async def __aenter__(self) -> Self:
        """Async context manager entry."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        """Async context manager exit."""
        await self.close()

    def _parse_ndjson(self, text: str) -> list[dict[str, Any]]:
        """Deprecated shim; delegates to api.parsing.parse_ndjson."""
        return parse_ndjson(text, self.logger)

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ) -> Any:
        """Make an HTTP request with rate limiting, retries, and error handling.

        Raises:
            RateLimitError, ServiceUnavailableError, LitVarAPIError.
        """
        await self._apply_rate_limit()
        url = urljoin(self.config.base_url, endpoint)
        start_time = time.time()
        last_error: Exception | None = None

        for attempt in range(self.config.max_retries + 1):
            try:
                response = await self._send_request_once(method, url, params, data)
                return self._handle_response(response, url, method, start_time)
            except (DisallowedURLError, ResponseTooLargeError) as exc:
                # Deterministic outbound URL/size POLICY violation on some hop
                # (F-07): NON-RETRYABLE. Map to UpstreamPolicyError so the MCP
                # layer classifies it retryable=False (a bare, status-less
                # LitVarAPIError maps to a transient/retryable upstream fault).
                # Chain with ``from None`` (NEVER ``from exc``) so no
                # __cause__/__context__ can carry the attacker-controlled host up
                # the stack into a chained ``logger.exception`` (e.g. the REST
                # ``_api_error_handler``). Log ONLY the exception type and the
                # (allowlisted, host-free) original request path.
                if self.logger:
                    self.logger.warning(
                        "Outbound request blocked by URL/size policy",
                        error_type=type(exc).__name__,
                        path=urlsplit(url).path,
                    )
                raise UpstreamPolicyError(
                    "LitVar2 request blocked by the outbound URL/size policy.",
                ) from None
            except (LitVarAPIError, RateLimitError, ServiceUnavailableError):
                raise
            except httpx.TimeoutException as exc:
                last_error = ServiceUnavailableError(f"Request timeout: {url}")
                self._log_attempt_error(exc, url, attempt)
            except httpx.NetworkError as exc:
                last_error = ServiceUnavailableError(f"Network error: {exc!s}")
                self._log_attempt_error(exc, url, attempt)
            except Exception as exc:  # boundary, re-raised below
                last_error = LitVarAPIError(f"Unexpected error: {exc!s}")
                self._log_attempt_error(exc, url, attempt)
            if attempt < self.config.max_retries:
                await asyncio.sleep(
                    backoff_delay(base=self.config.retry_delay, attempt=attempt),
                )

        self._record_failure(url, method, start_time, last_error)
        raise last_error or LitVarAPIError("Request failed after all retries")

    async def _apply_rate_limit(self) -> None:
        """Acquire a rate-limit token and sleep if throttled."""
        wait_time = await self.rate_limiter.acquire()
        if wait_time > 0:
            if self.logger:
                self.logger.debug("Rate limit applied", wait_time=wait_time)
            await asyncio.sleep(wait_time)

    async def _send_request_once(
        self,
        method: str,
        url: str,
        params: dict[str, Any] | None,
        data: dict[str, Any] | None,
    ) -> httpx.Response:
        """Send a single HTTP attempt (no retry, no parsing)."""
        return await self.client.request(method=method, url=url, params=params, json=data)

    def _handle_response(
        self,
        response: httpx.Response,
        url: str,
        method: str,
        start_time: float,
    ) -> Any:
        """Classify status, record stats, and parse the body of one response."""
        response_time = time.time() - start_time
        if self.logger:
            log_api_request(self.logger, method, url, response_time, response.status_code)
        retry_after = (
            float(response.headers.get("Retry-After", 0)) or None
            if response.status_code == HTTP_TOO_MANY_REQUESTS
            else None
        )
        raise_for_status_code(
            response.status_code,
            url=url,
            text=response.text,
            retry_after=retry_after,
        )
        response.raise_for_status()
        self._record_success(response_time)
        return parse_response_body(
            content_type=response.headers.get("content-type", "").lower(),
            response_text=response.text,
            json_loader=response.json,
            logger=self.logger,
        )

    def _record_success(self, response_time: float) -> None:
        """Update success counters and the bounded response-time window."""
        self.total_requests += 1
        self.successful_requests += 1
        self._append_response_time(response_time)

    def _record_failure(
        self,
        url: str,
        method: str,
        start_time: float,
        last_error: Exception | None,
    ) -> None:
        """Update failure counters and log the exhausted-retries event."""
        response_time = time.time() - start_time
        self.total_requests += 1
        self._append_response_time(response_time)
        if self.logger:
            log_api_request(
                self.logger,
                method,
                url,
                response_time,
                0,
                error=str(last_error) if last_error else "Unknown error",
            )

    def _append_response_time(self, response_time: float) -> None:
        """Append to the response-time window, keeping the last 100."""
        self.response_times.append(response_time)
        if len(self.response_times) > self._RESPONSE_TIME_WINDOW:
            self.response_times = self.response_times[-self._RESPONSE_TIME_WINDOW :]

    def _log_attempt_error(self, exc: Exception, url: str, attempt: int) -> None:
        """Log a per-attempt error with context."""
        if self.logger:
            log_error_with_context(
                self.logger,
                exc,
                "http_request",
                {"url": url, "attempt": attempt + 1},
            )

    async def search_variants(
        self,
        query: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Search variants using autocomplete endpoint.

        Args:
            query: Search query
            limit: Maximum number of results

        Returns:
            List of variant dictionaries

        Raises:
            ValueError: If query is empty or too long, or limit is out of range
        """
        query = validate_query(query)
        limit = validate_limit(limit)

        endpoint = self.config.endpoints["autocomplete"]
        params = {"query": query, "limit": limit}

        response = await self._make_request("GET", endpoint, params=params)
        return cast("list[dict[str, Any]]", extract_list(response, key="results"))

    async def get_variant_details(self, variant_id: str) -> dict[str, Any]:
        """Get detailed information about a variant.

        Args:
            variant_id: Unique variant identifier

        Returns:
            Variant details dictionary
        """
        endpoint = _format_endpoint(
            self.config.endpoints["variant_details"],
            variant_id=variant_id,
        )
        return cast("dict[str, Any]", await self._make_request("GET", endpoint))

    async def get_variant_publications(self, variant_id: str) -> list[str]:
        """Get publications associated with a variant.

        Args:
            variant_id: Unique variant identifier

        Returns:
            List of PMIDs
        """
        endpoint = _format_endpoint(
            self.config.endpoints["variant_publications"],
            variant_id=variant_id,
        )
        response = await self._make_request("GET", endpoint)
        # LitVar2 returns PMIDs as integers; coerce to honour the list[str]
        # contract (Publication.pmid is a str).
        return [str(pmid) for pmid in extract_list(response, key="pmids")]

    async def sensor_lookup(self, rsid: str) -> dict[str, Any] | None:
        """Check if RSID is available in LitVar2.

        Args:
            rsid: Reference SNP ID

        Returns:
            Sensor response dictionary

        Raises:
            ValueError: If RSID format is invalid
        """
        rsid = validate_rsid(rsid)
        endpoint = _format_endpoint(self.config.endpoints["sensor"], rsid=rsid)
        return cast("dict[str, Any] | None", await self._make_request("GET", endpoint))

    async def get_variants_by_gene(self, gene_name: str) -> list[dict[str, Any]]:
        """Get all variants for a specific gene.

        Args:
            gene_name: Gene symbol

        Returns:
            List of variant dictionaries

        Raises:
            ValueError: If gene name is empty or too long
        """
        gene_name = validate_gene_name(gene_name)
        endpoint = _format_endpoint(
            self.config.endpoints["gene_variants"],
            gene_name=gene_name,
        )
        response = await self._make_request("GET", endpoint)
        return cast("list[dict[str, Any]]", extract_list(response, key="variants"))

    async def health_check(self) -> dict[str, Any]:
        """Perform health check on LitVar2 API.

        Returns:
            Health status dictionary
        """
        try:
            # Use a simple autocomplete query as health check
            start_time = time.time()
            await self.search_variants("rs", limit=1)
            response_time = time.time() - start_time

            return {
                "status": "healthy",
                "response_time_ms": round(response_time * 1000, 2),
                "rate_limiter_tokens": self.rate_limiter.current_tokens,
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "error_type": type(e).__name__,
            }

    def get_stats(self) -> dict[str, Any]:
        """Get client statistics.

        Returns:
            Dictionary containing request statistics
        """
        avg_response_time = 0.0
        if self.response_times:
            avg_response_time = sum(self.response_times) / len(self.response_times)

        success_rate = 0.0
        if self.total_requests > 0:
            success_rate = (self.successful_requests / self.total_requests) * 100.0

        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "success_rate": success_rate,
            "avg_response_time": avg_response_time,
            "current_rate": self.rate_limiter.current_rate(),
        }
