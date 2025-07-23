"""LitVar2 API client with rate limiting and error handling."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any
from urllib.parse import urljoin

import httpx
from structlog.typing import FilteringBoundLogger

from ..config import APIConfig
from ..exceptions import LitVarAPIError, RateLimitError, ServiceUnavailableError
from ..logging_config import log_api_request, log_error_with_context


class TokenBucketRateLimiter:
    """Token bucket rate limiter for API requests."""

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
                return 0.0
            # Calculate wait time for next token
            wait_time = (1 - self.tokens) / self.rate
            return wait_time

    @property
    def current_tokens(self) -> float:
        """Get current number of available tokens."""
        now = time.time()
        elapsed = now - self.last_update
        return min(self.burst, self.tokens + elapsed * self.rate)


class LitVar2Client:
    """HTTP client for LitVar2 API with rate limiting and error handling."""

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

    async def __aenter__(self) -> LitVar2Client:
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
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
        for line in text.strip().split("\n"):
            line = line.strip()
            if line:
                try:
                    # Try parsing as-is first
                    results.append(json.loads(line))
                except json.JSONDecodeError:
                    try:
                        # LitVar2 API returns Python-style dict syntax (single quotes)
                        # Convert to valid JSON by replacing single quotes with double quotes  # noqa: E501
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
                if response.status_code == 429:
                    retry_after = float(response.headers.get("Retry-After", 60))
                    raise RateLimitError(
                        f"Rate limit exceeded for {url}",
                        retry_after=retry_after,
                    )
                if response.status_code >= 500:
                    raise ServiceUnavailableError(
                        f"LitVar2 service error: HTTP {response.status_code}",
                    )
                if response.status_code >= 400:
                    error_text = (
                        response.text[:200] if response.text else "Unknown error"
                    )
                    raise LitVarAPIError(
                        f"HTTP {response.status_code}: {error_text}",
                        status_code=response.status_code,
                    )

                response.raise_for_status()

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
        """
        endpoint = self.config.endpoints["autocomplete"]
        params = {"query": query, "limit": limit}

        response = await self._make_request("GET", endpoint, params=params)

        # Handle different response formats
        if isinstance(response, list):
            return response
        if isinstance(response, dict) and "results" in response:
            return response["results"]
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
        return await self._make_request("GET", endpoint)

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
            return response.get("pmids", [])
        return []

    async def sensor_lookup(self, rsid: str) -> dict[str, Any]:
        """Check if RSID is available in LitVar2.

        Args:
            rsid: Reference SNP ID

        Returns:
            Sensor response dictionary
        """
        endpoint = self.config.endpoints["sensor"].format(rsid=rsid)
        return await self._make_request("GET", endpoint)

    async def get_variants_by_gene(self, gene_name: str) -> list[dict[str, Any]]:
        """Get all variants for a specific gene.

        Args:
            gene_name: Gene symbol

        Returns:
            List of variant dictionaries
        """
        endpoint = self.config.endpoints["gene_variants"].format(gene_name=gene_name)
        response = await self._make_request("GET", endpoint)

        # Handle different response formats
        if isinstance(response, list):
            return response
        if isinstance(response, dict) and "variants" in response:
            return response["variants"]
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
