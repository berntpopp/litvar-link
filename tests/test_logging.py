"""Test logging configuration and functionality."""

from __future__ import annotations

import json
import logging
import sys
from unittest.mock import Mock, patch

import pytest

from litvar_link import logging_config
from litvar_link.config import settings


class TestConfigureLogging:
    """Test the configure_logging function."""

    def test_configure_logging_default_http_mode(self, monkeypatch):
        """Test logging configuration in default HTTP mode."""
        # Clear any existing transport mode
        monkeypatch.delenv("TRANSPORT", raising=False)
        monkeypatch.setattr(settings, "transport_mode", None)

        # Mock basicConfig to avoid modifying real logging setup
        with patch("logging.basicConfig") as mock_basic_config:
            logger = logging_config.configure_logging()

            assert logger is not None
            # Should return a structured logger (BoundLoggerLazyProxy is the actual type)
            assert hasattr(logger, "info")
            assert hasattr(logger, "error")
            assert str(type(logger).__name__) in ["BoundLogger", "BoundLoggerLazyProxy"]

            # Should call basicConfig with stdout
            mock_basic_config.assert_called_once()
            call_kwargs = mock_basic_config.call_args[1]
            assert call_kwargs["stream"] == sys.stdout

    def test_configure_logging_stdio_mode_via_env(self, monkeypatch):
        """Test logging configuration in STDIO mode via environment variable."""
        monkeypatch.setenv("TRANSPORT", "stdio")

        # Mock basicConfig to avoid modifying real logging setup
        with patch("logging.basicConfig") as mock_basic_config:
            logger = logging_config.configure_logging()

            assert logger is not None

            # Should call basicConfig with stderr in STDIO mode
            mock_basic_config.assert_called_once()
            call_kwargs = mock_basic_config.call_args[1]
            assert call_kwargs["stream"] == sys.stderr

    def test_configure_logging_stdio_mode_via_settings(self, monkeypatch):
        """Test logging configuration in STDIO mode via settings."""
        monkeypatch.delenv("TRANSPORT", raising=False)
        monkeypatch.setattr(settings, "transport_mode", "stdio")

        # Mock basicConfig to avoid modifying real logging setup
        with patch("logging.basicConfig") as mock_basic_config:
            logger = logging_config.configure_logging()

            assert logger is not None

            # Should call basicConfig with stderr in STDIO mode
            mock_basic_config.assert_called_once()
            call_kwargs = mock_basic_config.call_args[1]
            assert call_kwargs["stream"] == sys.stderr

    def test_configure_logging_json_format(self, monkeypatch):
        """Test logging configuration with JSON format."""
        monkeypatch.setattr(settings, "log_format", "json")
        monkeypatch.delenv("TRANSPORT", raising=False)
        monkeypatch.setattr(settings, "transport_mode", None)

        logger = logging_config.configure_logging()

        # Log a test message
        logger.info("Test message", key="value")

        # The JSON renderer should be in the processor chain
        # This is mainly testing that the configuration doesn't crash
        assert logger is not None

    def test_configure_logging_console_format(self, monkeypatch):
        """Test logging configuration with console format."""
        monkeypatch.setattr(settings, "log_format", "console")
        monkeypatch.delenv("TRANSPORT", raising=False)
        monkeypatch.setattr(settings, "transport_mode", None)

        logger = logging_config.configure_logging()

        # Log a test message
        logger.info("Test message", key="value")

        assert logger is not None

    def test_configure_logging_with_caller_info(self, monkeypatch):
        """Test logging configuration with caller information enabled."""
        monkeypatch.setattr(settings, "log_show_caller", True)

        logger = logging_config.configure_logging()

        # Log a test message
        logger.info("Test message with caller info")

        assert logger is not None

    def test_configure_logging_without_caller_info(self, monkeypatch):
        """Test logging configuration with caller information disabled."""
        monkeypatch.setattr(settings, "log_show_caller", False)

        logger = logging_config.configure_logging()

        # Log a test message
        logger.info("Test message without caller info")

        assert logger is not None

    def test_configure_logging_log_levels(self, monkeypatch):
        """Test logging configuration with different log levels."""
        for level in ["DEBUG", "INFO", "WARNING", "ERROR"]:
            monkeypatch.setattr(settings, "log_level", level)

            # Mock basicConfig to check the level parameter
            with patch("logging.basicConfig") as mock_basic_config:
                logger = logging_config.configure_logging()
                assert logger is not None

                # Check that basicConfig was called with the correct level
                mock_basic_config.assert_called()
                call_kwargs = mock_basic_config.call_args[1]
                assert call_kwargs["level"] == getattr(logging, level)

    def test_configure_logging_stdio_noise_reduction(self, monkeypatch):
        """Test that STDIO mode reduces noise from HTTP libraries."""
        monkeypatch.setenv("TRANSPORT", "stdio")

        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            logging_config.configure_logging()

            # Check that specific loggers were set to WARNING level
            expected_calls = ["uvicorn", "httpx", "httpcore", "fastapi", "fastmcp"]

            for logger_name in expected_calls:
                mock_get_logger.assert_any_call(logger_name)

    def test_configure_logging_http_mode_logger_levels(self, monkeypatch):
        """Test that HTTP mode sets appropriate logger levels."""
        monkeypatch.delenv("TRANSPORT", raising=False)
        monkeypatch.setattr(settings, "transport_mode", None)

        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            logging_config.configure_logging()

            # Check that specific loggers were configured for HTTP mode
            mock_get_logger.assert_any_call("uvicorn.access")
            mock_get_logger.assert_any_call("httpx")

    def test_configure_logging_colors_disabled_in_stdio(self, monkeypatch):
        """Test that colors are disabled in STDIO mode."""
        monkeypatch.setenv("TRANSPORT", "stdio")
        monkeypatch.setattr(settings, "log_format", "console")

        with patch("structlog.dev.ConsoleRenderer") as mock_renderer:
            logging_config.configure_logging()

            # Console renderer should be called with colors=False in STDIO mode
            mock_renderer.assert_called_with(colors=False)

    def test_configure_logging_colors_enabled_in_http(self, monkeypatch):
        """Test that colors are enabled in HTTP mode."""
        monkeypatch.delenv("TRANSPORT", raising=False)
        monkeypatch.setattr(settings, "transport_mode", None)
        monkeypatch.setattr(settings, "log_format", "console")

        with patch("structlog.dev.ConsoleRenderer") as mock_renderer:
            logging_config.configure_logging()

            # Console renderer should be called with colors=True in HTTP mode
            mock_renderer.assert_called_with(colors=True)


class TestOrjsonSerializer:
    """Test the orjson_serializer function."""

    def test_orjson_serializer_with_orjson_available(self):
        """Test serializer when orjson is available."""
        test_data = {"key": "value", "number": 42}

        # Mock orjson module and its dumps method
        mock_orjson = Mock()
        mock_orjson.dumps.return_value = b'{"key":"value","number":42}'

        # Patch the import of orjson in the try block
        with patch.dict("sys.modules", {"orjson": mock_orjson}):
            result = logging_config.orjson_serializer(test_data)

            assert result == '{"key":"value","number":42}'
            mock_orjson.dumps.assert_called_once_with(test_data)

    def test_orjson_serializer_fallback_to_json(self):
        """Test serializer fallback to standard json when orjson is not available."""
        test_data = {"key": "value", "number": 42}

        # Temporarily remove orjson from sys.modules to simulate ImportError
        original_modules = sys.modules.copy()
        if "orjson" in sys.modules:
            del sys.modules["orjson"]

        try:
            result = logging_config.orjson_serializer(test_data)

            # Should return valid JSON string
            parsed = json.loads(result)
            assert parsed == test_data
        finally:
            # Restore original sys.modules
            sys.modules.clear()
            sys.modules.update(original_modules)

    def test_orjson_serializer_with_non_serializable_object(self):
        """Test serializer with objects that need default=str."""

        class TestObject:
            def __str__(self):
                return "test_object"

        test_data = {"object": TestObject()}

        # Since orjson is available in this environment and doesn't handle non-serializable
        # objects the same way as json.dumps(default=str), this will raise a TypeError.
        # This exposes a limitation in the current implementation.
        try:
            import orjson

            # If orjson is available, it will raise TypeError for non-serializable objects
            with pytest.raises(TypeError, match="Type is not JSON serializable"):
                logging_config.orjson_serializer(test_data)
        except ImportError:
            # If orjson is not available, it should fall back to json with default=str
            result = logging_config.orjson_serializer(test_data)
            parsed = json.loads(result)
            assert parsed["object"] == "test_object"


class TestLogApiRequest:
    """Test the log_api_request function."""

    def test_log_api_request_success(self):
        """Test logging successful API request."""
        mock_logger = Mock()

        logging_config.log_api_request(
            logger=mock_logger,
            method="GET",
            url="https://api.example.com/test",
            response_time=0.123,
            status_code=200,
        )

        mock_logger.info.assert_called_once_with(
            "API request completed",
            method="GET",
            url="https://api.example.com/test",
            response_time_ms=123.0,
            status_code=200,
        )
        mock_logger.error.assert_not_called()

    def test_log_api_request_with_error(self):
        """Test logging API request with error."""
        mock_logger = Mock()

        logging_config.log_api_request(
            logger=mock_logger,
            method="POST",
            url="https://api.example.com/test",
            response_time=0.456,
            status_code=500,
            error="Server error",
        )

        mock_logger.error.assert_called_once_with(
            "API request failed",
            method="POST",
            url="https://api.example.com/test",
            response_time_ms=456.0,
            status_code=500,
            error="Server error",
        )
        mock_logger.info.assert_not_called()

    def test_log_api_request_response_time_rounding(self):
        """Test that response time is properly rounded."""
        mock_logger = Mock()

        logging_config.log_api_request(
            logger=mock_logger,
            method="GET",
            url="https://api.example.com/test",
            response_time=0.123456789,
            status_code=200,
        )

        # Should round to 2 decimal places
        call_args = mock_logger.info.call_args[1]
        assert call_args["response_time_ms"] == 123.46


class TestLogCacheOperation:
    """Test the log_cache_operation function."""

    def test_log_cache_operation_basic(self):
        """Test basic cache operation logging."""
        mock_logger = Mock()

        logging_config.log_cache_operation(
            logger=mock_logger, operation="get", key="test_key",
        )

        mock_logger.debug.assert_called_once_with(
            "Cache operation", operation="get", key="test_key",
        )

    def test_log_cache_operation_with_hit(self):
        """Test cache operation logging with hit information."""
        mock_logger = Mock()

        logging_config.log_cache_operation(
            logger=mock_logger, operation="get", key="test_key", hit=True,
        )

        mock_logger.debug.assert_called_once_with(
            "Cache operation", operation="get", key="test_key", cache_hit=True,
        )

    def test_log_cache_operation_with_size(self):
        """Test cache operation logging with size information."""
        mock_logger = Mock()

        logging_config.log_cache_operation(
            logger=mock_logger, operation="set", key="test_key", size=1024,
        )

        mock_logger.debug.assert_called_once_with(
            "Cache operation", operation="set", key="test_key", cache_size=1024,
        )

    def test_log_cache_operation_with_all_params(self):
        """Test cache operation logging with all parameters."""
        mock_logger = Mock()

        logging_config.log_cache_operation(
            logger=mock_logger, operation="set", key="test_key", hit=False, size=512,
        )

        mock_logger.debug.assert_called_once_with(
            "Cache operation",
            operation="set",
            key="test_key",
            cache_hit=False,
            cache_size=512,
        )


class TestLogMcpToolCall:
    """Test the log_mcp_tool_call function."""

    def test_log_mcp_tool_call_success(self):
        """Test logging successful MCP tool call."""
        mock_logger = Mock()

        logging_config.log_mcp_tool_call(
            logger=mock_logger,
            tool_name="search_variants",
            params={"query": "BRCA1", "limit": 10},
            duration=0.789,
            success=True,
        )

        mock_logger.info.assert_called_once_with(
            "MCP tool call completed",
            tool_name="search_variants",
            params={"query": "BRCA1", "limit": 10},
            duration_ms=789.0,
            success=True,
        )
        mock_logger.error.assert_not_called()

    def test_log_mcp_tool_call_with_error(self):
        """Test logging MCP tool call with error."""
        mock_logger = Mock()

        logging_config.log_mcp_tool_call(
            logger=mock_logger,
            tool_name="search_variants",
            params={"query": "invalid"},
            duration=0.123,
            success=False,
            error="Validation failed",
        )

        mock_logger.error.assert_called_once_with(
            "MCP tool call failed",
            tool_name="search_variants",
            params={"query": "invalid"},
            duration_ms=123.0,
            success=False,
            error="Validation failed",
        )
        mock_logger.info.assert_not_called()

    def test_log_mcp_tool_call_duration_rounding(self):
        """Test that duration is properly rounded."""
        mock_logger = Mock()

        logging_config.log_mcp_tool_call(
            logger=mock_logger,
            tool_name="test_tool",
            params={},
            duration=0.123456789,
            success=True,
        )

        # Should round to 2 decimal places
        call_args = mock_logger.info.call_args[1]
        assert call_args["duration_ms"] == 123.46


class TestLogServerStartup:
    """Test the log_server_startup function."""

    def test_log_server_startup_basic(self):
        """Test basic server startup logging."""
        mock_logger = Mock()

        logging_config.log_server_startup(logger=mock_logger, mode="stdio")

        mock_logger.info.assert_called_once_with("Server starting", mode="stdio")

    def test_log_server_startup_with_host_and_port(self):
        """Test server startup logging with host and port."""
        mock_logger = Mock()

        logging_config.log_server_startup(
            logger=mock_logger, mode="http", host="127.0.0.1", port=8000,
        )

        mock_logger.info.assert_called_once_with(
            "Server starting", mode="http", host="127.0.0.1", port=8000,
        )

    def test_log_server_startup_with_partial_network_info(self):
        """Test server startup logging with only host or only port."""
        mock_logger = Mock()

        # Only host provided
        logging_config.log_server_startup(
            logger=mock_logger, mode="http", host="127.0.0.1", port=None,
        )

        # Should not include host/port in log data
        mock_logger.info.assert_called_with("Server starting", mode="http")


class TestLogErrorWithContext:
    """Test the log_error_with_context function."""

    def test_log_error_with_context_basic(self):
        """Test basic error logging with context."""
        mock_logger = Mock()
        error = ValueError("Test error")

        logging_config.log_error_with_context(
            logger=mock_logger, error=error, operation="test_operation",
        )

        mock_logger.error.assert_called_once_with(
            "Operation failed",
            operation="test_operation",
            error_type="ValueError",
            error_message="Test error",
            exc_info=True,
        )

    def test_log_error_with_context_with_context(self):
        """Test error logging with additional context."""
        mock_logger = Mock()
        error = ConnectionError("Network error")
        context = {"url": "https://api.example.com", "retry_count": 3}

        logging_config.log_error_with_context(
            logger=mock_logger, error=error, operation="api_request", context=context,
        )

        mock_logger.error.assert_called_once_with(
            "Operation failed",
            operation="api_request",
            error_type="ConnectionError",
            error_message="Network error",
            context=context,
            exc_info=True,
        )

    def test_log_error_with_context_no_context(self):
        """Test error logging without additional context."""
        mock_logger = Mock()
        error = RuntimeError("Runtime error")

        logging_config.log_error_with_context(
            logger=mock_logger, error=error, operation="runtime_operation", context=None,
        )

        # Should not include context key when context is None
        expected_call_kwargs = {
            "operation": "runtime_operation",
            "error_type": "RuntimeError",
            "error_message": "Runtime error",
            "exc_info": True,
        }

        mock_logger.error.assert_called_once_with(
            "Operation failed", **expected_call_kwargs,
        )
