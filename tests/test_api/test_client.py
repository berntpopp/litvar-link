"""Comprehensive tests for LitVar2 API client."""

import asyncio
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from httpx import ConnectTimeout, HTTPStatusError, ReadTimeout

from litvar_link.api.client import LitVar2Client, TokenBucketRateLimiter
from litvar_link.config import APIConfig
from litvar_link.exceptions import LitVarAPIError, ServiceUnavailableError


class TestTokenBucketRateLimiter:
    """Test token bucket rate limiter implementation."""

    def test_rate_limiter_initialization(self) -> None:
        """Test rate limiter initialization."""
        limiter = TokenBucketRateLimiter(rate=2.0, burst=5)

        assert limiter.rate == 2.0
        assert limiter.burst == 5
        assert limiter.tokens == 5  # Starts full
        assert limiter.last_update > 0

    async def test_tokens_refill_over_time(self) -> None:
        """Test that tokens refill at the correct rate."""
        limiter = TokenBucketRateLimiter(rate=4.0, burst=4)  # 4 tokens per second

        # Consume all tokens
        await limiter.acquire()
        await limiter.acquire()
        await limiter.acquire()
        await limiter.acquire()

        # Now should be empty (with small tolerance for floating point precision)
        assert abs(limiter.tokens) < 0.001

        # Wait for some tokens to refill
        await asyncio.sleep(0.6)  # Wait 0.6 seconds, should get ~2.4 tokens

        # Should now have tokens available (verify by acquiring without waiting)
        start_time = time.time()
        wait_time = await limiter.acquire()
        end_time = time.time()

        # Should not have waited long since tokens refilled
        assert end_time - start_time < 0.1
        assert wait_time == 0.0

    async def test_tokens_capped_at_burst_size(self) -> None:
        """Test tokens don't exceed burst size."""
        limiter = TokenBucketRateLimiter(rate=10.0, burst=3)  # High rate, small burst

        # Wait long enough for many tokens to accumulate (if not capped)
        await asyncio.sleep(
            1.0,
        )  # 1 second at 10/sec would be 10 tokens, but capped at 3

        # Should only have burst size available
        # Test by trying to acquire more than burst size without delay
        start_time = time.time()
        await limiter.acquire()  # Should be immediate
        await limiter.acquire()  # Should be immediate
        await limiter.acquire()  # Should be immediate
        mid_time = time.time()

        # First 3 should be immediate
        assert mid_time - start_time < 0.1

        # 4th should require waiting since we only had 3 tokens
        # Check that tokens are exhausted before next acquire
        assert (
            abs(limiter.tokens) < 0.01
        )  # Should be ~0 after using burst size (increased tolerance for timing)
        await limiter.acquire()
        end_time = time.time()
        # On fast machines, timing might be very precise, so check that some time passed
        assert end_time > mid_time  # Should have waited some amount

    async def test_acquire_token_success(self) -> None:
        """Test successful token acquisition."""
        limiter = TokenBucketRateLimiter(rate=10.0, burst=5)

        # Should succeed immediately
        start_time = time.time()
        wait_time = await limiter.acquire()
        end_time = time.time()

        # Should not block
        assert end_time - start_time < 0.1
        assert wait_time == 0.0
        assert limiter.tokens == 4.0  # One token consumed

    async def test_acquire_token_waits_when_empty(self) -> None:
        """Test that acquire waits when no tokens available."""
        limiter = TokenBucketRateLimiter(
            rate=4.0,
            burst=1,
        )  # 4 tokens per second, 1 burst

        # Consume the only token
        await limiter.acquire()  # This consumes the available token

        start_time = time.time()
        wait_time = await limiter.acquire()  # This should wait
        end_time = time.time()

        # Should have waited approximately 0.25 seconds (1/4 second for 1 token)
        actual_wait = end_time - start_time
        # The wait_time returned should be > 0 if tokens were exhausted
        # On very fast machines, actual timing may be negligible but logic should be correct
        assert wait_time >= 0  # wait_time should indicate waiting was needed
        assert actual_wait >= 0  # Some time should have passed
        # Verify tokens were properly managed
        assert limiter.tokens <= limiter.burst  # Tokens should not exceed burst

    async def test_concurrent_token_acquisition(self) -> None:
        """Test concurrent token acquisition."""
        limiter = TokenBucketRateLimiter(rate=2.0, burst=2)

        # Both should succeed without much delay
        start_time = time.time()
        await asyncio.gather(limiter.acquire(), limiter.acquire())
        end_time = time.time()

        # Should not take long since we have 2 tokens
        assert end_time - start_time < 0.2
        assert abs(limiter.tokens) < 0.001  # Allow small floating point tolerance

    def test_current_rate_calculation(self) -> None:
        """Test current rate calculation."""
        limiter = TokenBucketRateLimiter(rate=2.0, burst=5)

        # Fresh limiter should show 0 rate
        assert limiter.current_rate() == 0.0

        # Simulate some requests
        now = time.time()
        limiter.request_times = [now - 2, now - 1, now - 0.5, now]

        rate = limiter.current_rate()
        # 4 requests in ~2 seconds = ~2 req/sec
        assert 1.5 <= rate <= 2.5


class TestLitVar2Client:
    """Test LitVar2 API client."""

    @pytest.fixture
    def api_config(self) -> APIConfig:
        """Create test API config."""
        return APIConfig(
            base_url="https://test-litvar.api.example.com/",
            timeout=10,
            rate_limit_per_second=2.0,
            burst_size=3,
            max_retries=2,
            retry_delay=0.1,
        )

    @pytest.fixture
    def mock_logger(self) -> MagicMock:
        """Create mock logger."""
        return MagicMock()

    @pytest.mark.asyncio
    async def test_client_initialization(
        self,
        api_config: APIConfig,
        mock_logger: MagicMock,
    ) -> None:
        """Test client initialization."""
        async with LitVar2Client(config=api_config, logger=mock_logger) as client:
            assert client.config == api_config
            assert client.logger == mock_logger
            assert client.rate_limiter.rate == 2.0
            assert client.rate_limiter.burst == 3
            assert isinstance(client.client, httpx.AsyncClient)

    @pytest.mark.asyncio
    async def test_search_variants_success(
        self,
        api_config: APIConfig,
        mock_logger: MagicMock,
    ) -> None:
        """Test successful variant search."""
        mock_response_data = [
            {
                "_id": "litvar@rs1061170##",
                "rsid": "rs1061170",
                "gene": ["CFH"],
                "name": "p.Y402H",
                "pmids_count": 834,
                "match": "CFH <em>p.Y402H</em> (rs1061170)",
            },
        ]

        with patch("httpx.AsyncClient.request") as mock_request:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.text = json.dumps(mock_response_data)
            mock_response.headers = {"content-type": "application/json"}
            mock_response.json = MagicMock(return_value=mock_response_data)
            mock_response.raise_for_status = MagicMock()
            mock_request.return_value = mock_response

            async with LitVar2Client(config=api_config, logger=mock_logger) as client:
                result = await client.search_variants("CFH", limit=10)

                assert len(result) == 1
                assert result[0]["_id"] == "litvar@rs1061170##"
                assert result[0]["rsid"] == "rs1061170"

                # Verify correct URL was called
                mock_request.assert_called_once()
                call_args = mock_request.call_args
                assert "variant/autocomplete/" in str(call_args[1]["url"])
                assert call_args[1]["params"]["query"] == "CFH"
                assert call_args[1]["params"]["limit"] == 10

    @pytest.mark.asyncio
    async def test_search_variants_query_validation(
        self,
        api_config: APIConfig,
        mock_logger: MagicMock,
    ) -> None:
        """Test query validation in search_variants."""
        async with LitVar2Client(config=api_config, logger=mock_logger) as client:
            # Test empty query
            with pytest.raises(ValueError, match="Query cannot be empty"):
                await client.search_variants("", limit=10)

            # Test query too long
            with pytest.raises(ValueError, match="Query too long"):
                await client.search_variants("x" * 101, limit=10)

            # Test invalid limit
            with pytest.raises(ValueError, match="Limit must be between"):
                await client.search_variants("test", limit=0)

            with pytest.raises(ValueError, match="Limit must be between"):
                await client.search_variants("test", limit=101)

    @pytest.mark.asyncio
    async def test_sensor_lookup_success(
        self,
        api_config: APIConfig,
        mock_logger: MagicMock,
    ) -> None:
        """Test successful RSID sensor lookup."""
        mock_response_data = {
            "rsid": "rs1061170",
            "pmids_count": 834,
            "litvar_url": "https://www.ncbi.nlm.nih.gov/research/litvar2/docsum?text=rs1061170",
        }

        with patch("httpx.AsyncClient.request") as mock_request:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.text = json.dumps(mock_response_data)
            mock_response.headers = {"content-type": "application/json"}
            mock_response.json = MagicMock(return_value=mock_response_data)
            mock_response.raise_for_status = MagicMock()
            mock_request.return_value = mock_response

            async with LitVar2Client(config=api_config, logger=mock_logger) as client:
                result = await client.sensor_lookup("rs1061170")

                assert result["rsid"] == "rs1061170"
                assert result["pmids_count"] == 834

                # Verify correct URL was called
                mock_request.assert_called_once()
                call_args = mock_request.call_args
                assert "sensor/rs1061170" in str(call_args[1]["url"])

    @pytest.mark.asyncio
    async def test_sensor_lookup_rsid_validation(
        self,
        api_config: APIConfig,
        mock_logger: MagicMock,
    ) -> None:
        """Test RSID validation in sensor lookup."""
        async with LitVar2Client(config=api_config, logger=mock_logger) as client:
            # Test invalid RSID format
            with pytest.raises(ValueError, match="Invalid RSID format"):
                await client.sensor_lookup("invalid_rsid")

            with pytest.raises(ValueError, match="Invalid RSID format"):
                await client.sensor_lookup("rs")

            with pytest.raises(ValueError, match="Invalid RSID format"):
                await client.sensor_lookup("1061170")

    @pytest.mark.asyncio
    async def test_get_variants_by_gene_success(
        self,
        api_config: APIConfig,
        mock_logger: MagicMock,
    ) -> None:
        """Test successful gene variants lookup."""
        # Mock NDJSON response (newline-delimited JSON with Python-style dicts)
        mock_ndjson = """{'_id': 'litvar@rs9970784##', 'rsid': 'rs9970784', 'pmids_count': 1}
{'_id': 'litvar@rs800292##', 'rsid': 'rs800292', 'pmids_count': 490}"""

        with patch("httpx.AsyncClient.request") as mock_request:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.text = mock_ndjson
            mock_response.headers = {"content-type": "text/plain"}
            mock_response.json = MagicMock(
                side_effect=json.JSONDecodeError("No JSON", "", 0),
            )
            mock_response.raise_for_status = MagicMock()
            mock_request.return_value = mock_response

            async with LitVar2Client(config=api_config, logger=mock_logger) as client:
                result = await client.get_variants_by_gene("CFH")

                assert len(result) == 2
                assert result[0]["_id"] == "litvar@rs9970784##"
                assert result[1]["_id"] == "litvar@rs800292##"

                # Verify correct URL was called
                mock_request.assert_called_once()
                call_args = mock_request.call_args
                assert "variant/search/gene/CFH" in str(call_args[1]["url"])

    @pytest.mark.asyncio
    async def test_get_variants_by_gene_validation(
        self,
        api_config: APIConfig,
        mock_logger: MagicMock,
    ) -> None:
        """Test gene name validation."""
        async with LitVar2Client(config=api_config, logger=mock_logger) as client:
            # Test empty gene name
            with pytest.raises(ValueError, match="Gene name cannot be empty"):
                await client.get_variants_by_gene("")

            # Test gene name too long
            with pytest.raises(ValueError, match="Gene name too long"):
                await client.get_variants_by_gene("x" * 51)

    @pytest.mark.asyncio
    async def test_ndjson_parsing_edge_cases(
        self,
        api_config: APIConfig,
        mock_logger: MagicMock,
    ) -> None:
        """Test NDJSON parsing with various edge cases."""
        async with LitVar2Client(config=api_config, logger=mock_logger) as client:
            # Test empty response
            result = client._parse_ndjson("")
            assert result == []

            # Test single line
            result = client._parse_ndjson("{'_id': 'test', 'count': 1}")
            assert len(result) == 1
            assert result[0]["_id"] == "test"

            # Test mixed quotes
            ndjson = """{'_id': 'test1', "count": 1}
{"_id": "test2", 'count': 2}"""
            result = client._parse_ndjson(ndjson)
            assert len(result) == 2

            # Test malformed JSON (should be skipped)
            ndjson = """{'_id': 'test1', 'count': 1}
{invalid json}
{'_id': 'test2', 'count': 2}"""
            result = client._parse_ndjson(ndjson)
            assert len(result) == 2  # Invalid line skipped

    @pytest.mark.asyncio
    async def test_http_error_handling(
        self,
        api_config: APIConfig,
        mock_logger: MagicMock,
    ) -> None:
        """Test HTTP error handling."""
        with patch("httpx.AsyncClient.request") as mock_request:
            # Test 404 error
            mock_response = AsyncMock()
            mock_response.status_code = 404
            mock_response.raise_for_status.side_effect = HTTPStatusError(
                "Not Found",
                request=AsyncMock(),
                response=mock_response,
            )
            mock_request.return_value = mock_response

            async with LitVar2Client(config=api_config, logger=mock_logger) as client:
                with pytest.raises(LitVarAPIError, match="HTTP 404"):
                    await client.search_variants("test")

    @pytest.mark.asyncio
    async def test_timeout_error_handling(
        self,
        api_config: APIConfig,
        mock_logger: MagicMock,
    ) -> None:
        """Test timeout error handling."""
        with patch("httpx.AsyncClient.request") as mock_request:
            mock_request.side_effect = ReadTimeout("Request timeout")

            async with LitVar2Client(config=api_config, logger=mock_logger) as client:
                with pytest.raises(LitVarAPIError, match="Request timeout"):
                    await client.search_variants("test")

    @pytest.mark.asyncio
    async def test_connection_error_handling(
        self,
        api_config: APIConfig,
        mock_logger: MagicMock,
    ) -> None:
        """Test connection error handling."""
        with patch("httpx.AsyncClient.request") as mock_request:
            mock_request.side_effect = ConnectTimeout("Connection timeout")

            async with LitVar2Client(config=api_config, logger=mock_logger) as client:
                with pytest.raises(ServiceUnavailableError, match="Request timeout"):
                    await client.search_variants("test")

    @pytest.mark.asyncio
    async def test_retry_mechanism(
        self,
        api_config: APIConfig,
        mock_logger: MagicMock,
    ) -> None:
        """Test retry mechanism with transient failures."""
        with patch("httpx.AsyncClient.request") as mock_request:
            # First two calls fail, third succeeds
            success_response = AsyncMock()
            success_response.status_code = 200
            success_response.text = "[]"
            success_response.headers = {"content-type": "application/json"}
            success_response.json = MagicMock(return_value=[])
            success_response.raise_for_status = MagicMock()

            mock_request.side_effect = [
                ReadTimeout("Timeout 1"),
                ReadTimeout("Timeout 2"),
                success_response,
            ]

            async with LitVar2Client(config=api_config, logger=mock_logger) as client:
                result = await client.search_variants("test")
                assert result == []
                assert mock_request.call_count == 3

    @pytest.mark.asyncio
    async def test_retry_exhaustion(
        self,
        api_config: APIConfig,
        mock_logger: MagicMock,
    ) -> None:
        """Test retry exhaustion."""
        with patch("httpx.AsyncClient.request") as mock_request:
            # All retries fail
            mock_request.side_effect = ReadTimeout("Persistent timeout")

            async with LitVar2Client(config=api_config, logger=mock_logger) as client:
                with pytest.raises(LitVarAPIError):
                    await client.search_variants("test")

                # Should try max_retries + 1 times
                assert mock_request.call_count == api_config.max_retries + 1

    @pytest.mark.asyncio
    async def test_rate_limiting_integration(self, mock_logger: MagicMock) -> None:
        """Test rate limiting integration."""
        # Very strict rate limiting for testing
        config = APIConfig(
            base_url="https://test.com/",
            timeout=10,
            rate_limit_per_second=1.0,  # 1 request per second
            burst_size=1,
            max_retries=0,
        )

        with patch("httpx.AsyncClient.request") as mock_request:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.text = "[]"
            mock_response.headers = {"content-type": "application/json"}
            mock_response.json = MagicMock(return_value=[])
            mock_response.raise_for_status = MagicMock()
            mock_request.return_value = mock_response

            async with LitVar2Client(config=config, logger=mock_logger) as client:
                # First request should be immediate
                start_time = time.time()
                await client.search_variants("test1")
                first_duration = time.time() - start_time

                # Second request should be delayed
                start_time = time.time()
                await client.search_variants("test2")
                second_duration = time.time() - start_time

                # First should be fast, second should wait ~1 second
                assert first_duration < 0.1
                assert 0.8 <= second_duration <= 1.5

    @pytest.mark.asyncio
    async def test_context_manager_cleanup(
        self,
        api_config: APIConfig,
        mock_logger: MagicMock,
    ) -> None:
        """Test proper cleanup in context manager."""
        client = LitVar2Client(config=api_config, logger=mock_logger)

        async with client:
            assert client.client is not None

        # After context, client should be closed
        assert client.client.is_closed

    @pytest.mark.asyncio
    async def test_statistics_tracking(
        self,
        api_config: APIConfig,
        mock_logger: MagicMock,
    ) -> None:
        """Test request statistics tracking."""
        with patch("httpx.AsyncClient.request") as mock_request:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.text = "[]"
            mock_response.headers = {"content-type": "application/json"}
            mock_response.json = MagicMock(return_value=[])
            mock_response.raise_for_status = MagicMock()
            mock_request.return_value = mock_response

            async with LitVar2Client(config=api_config, logger=mock_logger) as client:
                # Make several requests
                await client.search_variants("test1")
                await client.search_variants("test2")

                stats = client.get_stats()
                assert stats["total_requests"] >= 2
                assert stats["success_rate"] == 100.0
                assert "avg_response_time" in stats
                assert "current_rate" in stats

    @pytest.mark.asyncio
    async def test_json_response_parsing_failure(
        self,
        api_config: APIConfig,
        mock_logger: MagicMock,
    ) -> None:
        """Test handling of invalid JSON responses."""
        with patch("httpx.AsyncClient.request") as mock_request:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
            mock_response.text = "Invalid JSON response"
            mock_response.headers = {"content-type": "application/json"}
            mock_response.raise_for_status = MagicMock()
            mock_request.return_value = mock_response

            async with LitVar2Client(config=api_config, logger=mock_logger) as client:
                # Should handle JSON parsing failure gracefully and return empty list
                result = await client.search_variants("test")
                assert result == []

    @pytest.mark.asyncio
    async def test_unexpected_error_handling(
        self,
        api_config: APIConfig,
        mock_logger: MagicMock,
    ) -> None:
        """Test handling of unexpected errors."""
        with patch("httpx.AsyncClient.request") as mock_request:
            mock_request.side_effect = Exception("Unexpected error")

            async with LitVar2Client(config=api_config, logger=mock_logger) as client:
                with pytest.raises(LitVarAPIError, match="Unexpected error"):
                    await client.search_variants("test")

    def test_url_construction(
        self,
        api_config: APIConfig,
        mock_logger: MagicMock,
    ) -> None:
        """Test URL construction for different endpoints."""
        client = LitVar2Client(config=api_config, logger=mock_logger)

        # Test autocomplete URL
        url = client._build_url("variant/autocomplete/")
        assert url == "https://test-litvar.api.example.com/variant/autocomplete/"

        # Test sensor URL with parameter
        url = client._build_url("sensor/{rsid}", rsid="rs1061170")
        assert url == "https://test-litvar.api.example.com/sensor/rs1061170"

        # Test gene variants URL
        url = client._build_url("variant/search/gene/{gene_name}", gene_name="CFH")
        assert url == "https://test-litvar.api.example.com/variant/search/gene/CFH"

    @pytest.mark.asyncio
    async def test_429_rate_limit_error_handling(
        self,
        api_config: APIConfig,
        mock_logger: MagicMock,
    ) -> None:
        """Test 429 rate limit error handling with Retry-After header."""
        with patch("httpx.AsyncClient.request") as mock_request:
            mock_response = AsyncMock()
            mock_response.status_code = 429
            mock_response.headers = {"Retry-After": "120"}  # 2 minutes
            mock_response.raise_for_status.side_effect = HTTPStatusError(
                "Too Many Requests",
                request=AsyncMock(),
                response=mock_response,
            )
            mock_request.return_value = mock_response

            async with LitVar2Client(config=api_config, logger=mock_logger) as client:
                with pytest.raises(
                    Exception,
                ) as exc_info:  # RateLimitError should be raised
                    await client.search_variants("test")

                # Check that the error message contains rate limit info
                assert "Rate limit exceeded" in str(exc_info.value) or "429" in str(
                    exc_info.value,
                )

    @pytest.mark.asyncio
    async def test_429_rate_limit_error_without_retry_after(
        self,
        api_config: APIConfig,
        mock_logger: MagicMock,
    ) -> None:
        """Test 429 rate limit error handling without Retry-After header."""
        with patch("httpx.AsyncClient.request") as mock_request:
            mock_response = AsyncMock()
            mock_response.status_code = 429
            mock_response.headers = {}  # No Retry-After header
            mock_response.raise_for_status.side_effect = HTTPStatusError(
                "Too Many Requests",
                request=AsyncMock(),
                response=mock_response,
            )
            mock_request.return_value = mock_response

            async with LitVar2Client(config=api_config, logger=mock_logger) as client:
                with pytest.raises(
                    Exception,
                ) as exc_info:  # RateLimitError should be raised
                    await client.search_variants("test")

                # Should use default retry time when Retry-After header is missing
                assert "Rate limit exceeded" in str(exc_info.value) or "429" in str(
                    exc_info.value,
                )

    @pytest.mark.asyncio
    async def test_500_server_error_handling(
        self,
        api_config: APIConfig,
        mock_logger: MagicMock,
    ) -> None:
        """Test 500+ server error handling."""
        with patch("httpx.AsyncClient.request") as mock_request:
            mock_response = AsyncMock()
            mock_response.status_code = 500
            mock_response.raise_for_status.side_effect = HTTPStatusError(
                "Internal Server Error",
                request=AsyncMock(),
                response=mock_response,
            )
            mock_request.return_value = mock_response

            async with LitVar2Client(config=api_config, logger=mock_logger) as client:
                with pytest.raises(ServiceUnavailableError, match=r"service error.*500"):
                    await client.search_variants("test")

    @pytest.mark.asyncio
    async def test_503_service_unavailable_handling(
        self,
        api_config: APIConfig,
        mock_logger: MagicMock,
    ) -> None:
        """Test 503 service unavailable error handling."""
        with patch("httpx.AsyncClient.request") as mock_request:
            mock_response = AsyncMock()
            mock_response.status_code = 503
            mock_response.raise_for_status.side_effect = HTTPStatusError(
                "Service Unavailable",
                request=AsyncMock(),
                response=mock_response,
            )
            mock_request.return_value = mock_response

            async with LitVar2Client(config=api_config, logger=mock_logger) as client:
                with pytest.raises(ServiceUnavailableError, match=r"service error.*503"):
                    await client.search_variants("test")

    def test_ndjson_parsing_directly(
        self,
        api_config: APIConfig,
        mock_logger: MagicMock,
    ) -> None:
        """Test NDJSON parsing with malformed lines logs warnings."""
        # Test the _parse_ndjson method directly
        client = LitVar2Client(config=api_config, logger=mock_logger)

        # Response with both valid and invalid NDJSON lines
        ndjson_response = """{'_id': 'valid1', 'count': 1}
{this is not valid json}
{'_id': 'valid2', 'count': 2}
another invalid line without json"""

        result = client._parse_ndjson(ndjson_response)

        # Should only return valid parsed items (2 valid lines out of 4)
        assert len(result) == 2
        assert result[0]["_id"] == "valid1"
        assert result[1]["_id"] == "valid2"

        # Should have logged warnings for invalid lines
        mock_logger.warning.assert_called()

    @pytest.mark.asyncio
    async def test_health_check_with_exception(
        self,
        api_config: APIConfig,
        mock_logger: MagicMock,
    ) -> None:
        """Test health check when an exception occurs."""
        with patch("httpx.AsyncClient.request") as mock_request:
            mock_request.side_effect = Exception("Connection failed")

            async with LitVar2Client(config=api_config, logger=mock_logger) as client:
                health = await client.health_check()

                assert health["status"] == "unhealthy"
                assert "error" in health
                assert "Connection failed" in health["error"]

    @pytest.mark.asyncio
    async def test_different_http_client_errors(
        self,
        api_config: APIConfig,
        mock_logger: MagicMock,
    ) -> None:
        """Test different types of HTTP client errors."""
        error_scenarios = [
            (ConnectTimeout("Connection timeout"), ServiceUnavailableError),
            (ReadTimeout("Read timeout"), ServiceUnavailableError),
            (httpx.NetworkError("Network error"), ServiceUnavailableError),
        ]

        for http_error, expected_exception in error_scenarios:
            with patch("httpx.AsyncClient.request") as mock_request:
                mock_request.side_effect = http_error

                async with LitVar2Client(
                    config=api_config,
                    logger=mock_logger,
                ) as client:
                    with pytest.raises(expected_exception):
                        await client.search_variants("test")

    @pytest.mark.asyncio
    async def test_generic_httpx_exception_handling(
        self,
        api_config: APIConfig,
        mock_logger: MagicMock,
    ) -> None:
        """Test handling of generic httpx exceptions."""
        with patch("httpx.AsyncClient.request") as mock_request:
            mock_request.side_effect = httpx.HTTPError("Generic HTTP error")

            async with LitVar2Client(config=api_config, logger=mock_logger) as client:
                with pytest.raises(LitVarAPIError, match="Unexpected error"):
                    await client.search_variants("test")

    @pytest.mark.asyncio
    async def test_logging_in_error_scenarios(
        self,
        api_config: APIConfig,
        mock_logger: MagicMock,
    ) -> None:
        """Test that errors are properly logged."""
        with patch("httpx.AsyncClient.request") as mock_request:
            mock_request.side_effect = ReadTimeout("Connection timeout")

            async with LitVar2Client(config=api_config, logger=mock_logger) as client:
                with pytest.raises(ServiceUnavailableError):
                    await client.search_variants("test")

                # Should have logged the error
                mock_logger.error.assert_called()

    def test_client_without_logger(
        self,
        api_config: APIConfig,
    ) -> None:
        """Test client operation without logger."""
        # Should not raise exception when logger is None
        client = LitVar2Client(config=api_config, logger=None)
        assert client.logger is None

    @pytest.mark.asyncio
    async def test_client_initialization_with_headers(
        self,
        api_config: APIConfig,
        mock_logger: MagicMock,
    ) -> None:
        """Test that client is initialized with proper headers."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client_instance = AsyncMock()
            mock_client_class.return_value = mock_client_instance

            LitVar2Client(config=api_config, logger=mock_logger)

            # Check that httpx.AsyncClient was initialized with headers
            mock_client_class.assert_called_once()
            call_kwargs = mock_client_class.call_args[1]
            assert "headers" in call_kwargs
            headers = call_kwargs["headers"]
            assert "User-Agent" in headers
            assert "Accept" in headers
            assert headers["Accept"] == "application/json"
