"""LitVar2 API client with rate limiting and error handling."""

from __future__ import annotations

import asyncio
import json
import time
from typing import TYPE_CHECKING, Any, Self, cast
from urllib.parse import urljoin

import httpx

from litvar_link.api.rate_limiter import TokenBucketRateLimiter
from litvar_link.exceptions import (
    LitVarAPIError,
    RateLimitError,
    ServiceUnavailableError,
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


class LitVar2Client:
    """HTTP client for LitVar2 API with rate limiting and error handling."""

    # HTTP status code constants
    _HTTP_TOO_MANY_REQUESTS = 429
    _HTTP_SERVER_ERROR = 500
    _HTTP_CLIENT_ERROR = 400

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

        # Initialize HTTP client
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(config.timeout),
            headers={
                "User-Agent": config.user_agent,
                "Accept": "application/json",
            },
            follow_redirects=True,
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
        """Parse newline-delimited JSON (NDJSON) response.

        The LitVar2 API returns Python-style dictionaries with single quotes,
        which need to be converted to valid JSON format.

        Args:
            text: Raw NDJSON text with one JSON object per line

        Returns:
            List of parsed JSON objects
        """
        results = []
        for raw_line in text.strip().split("\n"):
            line = raw_line.strip()
            if line:
                try:
                    # Try parsing as-is first
                    results.append(json.loads(line))
                except json.JSONDecodeError:
                    try:
                        # LitVar2 API returns Python-style dict syntax (single quotes)
                        # Convert to valid JSON by replacing single quotes with double quotes
                        # This is a bit hacky but works for the LitVar2 API format
                        json_line = line.replace("'", '"')
                        results.append(json.loads(json_line))
                    except json.JSONDecodeError as e:
                        if self.logger:
                            self.logger.warning(
                                "Failed to parse NDJSON line",
                                line=line[:100],
                                error=str(e),
                            )
                        continue
        return results

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ) -> Any:
        """Make HTTP request with rate limiting and error handling.

        Args:
            method: HTTP method
            endpoint: API endpoint
            params: URL parameters
            data: Request body data

        Returns:
            Response data

        Raises:
            RateLimitError: When rate limit is exceeded
            ServiceUnavailableError: When service is unavailable
            LitVarAPIError: For other API errors
        """
        # Apply rate limiting
        wait_time = await self.rate_limiter.acquire()
        if wait_time > 0:
            if self.logger:
                self.logger.debug("Rate limit applied", wait_time=wait_time)
            await asyncio.sleep(wait_time)

        # Construct full URL
        url = urljoin(self.config.base_url, endpoint)

        # Make request with retries
        last_error: Exception | None = None
        start_time = time.time()

        for attempt in range(self.config.max_retries + 1):
            try:
                response = await self.client.request(
                    method=method,
                    url=url,
                    params=params,
                    json=data,
                )

                response_time = time.time() - start_time

                # Log successful request
                if self.logger:
                    log_api_request(
                        self.logger,
                        method,
                        url,
                        response_time,
                        response.status_code,
                    )

                # Handle different status codes
                if response.status_code == self._HTTP_TOO_MANY_REQUESTS:
                    retry_after = float(response.headers.get("Retry-After", 60))
                    msg = f"Rate limit exceeded for {url}"
                    raise RateLimitError(
                        msg,
                        retry_after=retry_after,
                    )
                if response.status_code >= self._HTTP_SERVER_ERROR:
                    msg = f"LitVar2 service error: HTTP {response.status_code}"
                    raise ServiceUnavailableError(
                        msg,
                    )
                if response.status_code >= self._HTTP_CLIENT_ERROR:
                    error_text = response.text[:200] if response.text else "Unknown error"
                    msg = f"HTTP {response.status_code}: {error_text}"
                    raise LitVarAPIError(
                        msg,
                        status_code=response.status_code,
                    )

                response.raise_for_status()

                # Track successful request statistics
                self.total_requests += 1
                self.successful_requests += 1
                self.response_times.append(response_time)
                # Keep only recent response times (last 100 requests)
                if len(self.response_times) > 100:
                    self.response_times = self.response_times[-100:]

                # Parse response
                content_type = response.headers.get("content-type", "").lower()
                response_text = response.text.strip()

                # Try to parse JSON response (handles both regular JSON and NDJSON)
                if "application/json" in content_type or (
                    response_text and response_text.startswith("{")
                ):
                    try:
                        # Try to parse as single JSON object first
                        return response.json()
                    except (ValueError, json.JSONDecodeError):
                        # If it fails, try to parse as NDJSON (newline-delimited JSON)
                        if "\n" in response_text:
                            return self._parse_ndjson(response_text)
                        # If it's not NDJSON either, re-raise the original error
                        raise

                return {"content": response_text, "content_type": content_type}

            except httpx.TimeoutException as e:
                last_error = ServiceUnavailableError(f"Request timeout: {url}")
                if self.logger:
                    log_error_with_context(
                        self.logger,
                        e,
                        "http_request",
                        {"url": url, "attempt": attempt + 1},
                    )
            except httpx.NetworkError as e:
                last_error = ServiceUnavailableError(f"Network error: {e!s}")
                if self.logger:
                    log_error_with_context(
                        self.logger,
                        e,
                        "http_request",
                        {"url": url, "attempt": attempt + 1},
                    )
            except (LitVarAPIError, RateLimitError, ServiceUnavailableError):
                # Don't retry these errors
                raise
            except Exception as e:
                last_error = LitVarAPIError(f"Unexpected error: {e!s}")
                if self.logger:
                    log_error_with_context(
                        self.logger,
                        e,
                        "http_request",
                        {"url": url, "attempt": attempt + 1},
                    )

            # Wait before retry
            if attempt < self.config.max_retries:
                await asyncio.sleep(self.config.retry_delay * (2**attempt))

        # All retries exhausted
        response_time = time.time() - start_time

        # Track failed request statistics
        self.total_requests += 1
        self.response_times.append(response_time)
        # Keep only recent response times (last 100 requests)
        if len(self.response_times) > 100:
            self.response_times = self.response_times[-100:]

        if self.logger:
            log_api_request(
                self.logger,
                method,
                url,
                response_time,
                0,
                error=str(last_error) if last_error else "Unknown error",
            )

        raise last_error or LitVarAPIError("Request failed after all retries")

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

        # Handle different response formats
        if isinstance(response, list):
            return response
        if isinstance(response, dict) and "results" in response:
            return cast("list[dict[str, Any]]", response["results"])
        return []

    async def get_variant_details(self, variant_id: str) -> dict[str, Any]:
        """Get detailed information about a variant.

        Args:
            variant_id: Unique variant identifier

        Returns:
            Variant details dictionary
        """
        endpoint = self.config.endpoints["variant_details"].format(
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
        endpoint = self.config.endpoints["variant_publications"].format(
            variant_id=variant_id,
        )
        response = await self._make_request("GET", endpoint)

        # Handle different response formats
        if isinstance(response, list):
            return response
        if isinstance(response, dict):
            return cast("list[str]", response.get("pmids", []))
        return []

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
        endpoint = self.config.endpoints["sensor"].format(rsid=rsid)
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
        endpoint = self.config.endpoints["gene_variants"].format(
            gene_name=gene_name,
        )
        response = await self._make_request("GET", endpoint)

        # Handle different response formats
        if isinstance(response, list):
            return response
        if isinstance(response, dict) and "variants" in response:
            return cast("list[dict[str, Any]]", response["variants"])
        return []

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

    def _build_url(self, endpoint: str, **kwargs: Any) -> str:
        """Build full URL from endpoint template.

        Args:
            endpoint: Endpoint template with placeholders
            **kwargs: Values to substitute in template

        Returns:
            Full URL
        """
        formatted_endpoint = endpoint.format(**kwargs)
        return urljoin(self.config.base_url, formatted_endpoint)
