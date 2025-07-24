"""Structured logging configuration for LitVar-Link."""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING, Any

import structlog

from .config import settings

if TYPE_CHECKING:
    from structlog.typing import FilteringBoundLogger


def configure_logging() -> FilteringBoundLogger:
    """Configure structured logging with structlog."""
    # Determine if we're in STDIO mode by checking environment variable or config
    import os

    is_stdio_mode = (
        os.environ.get("TRANSPORT") == "stdio"
        or getattr(settings, "transport_mode", None) == "stdio"
    )

    # For MCP/STDIO mode, use stderr to avoid interfering with the JSON protocol
    # For HTTP mode, use stdout for normal logging
    log_stream = sys.stderr if is_stdio_mode else sys.stdout

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=log_stream,
        level=getattr(logging, settings.log_level),
    )

    # Reduce noise from HTTP libraries in STDIO mode
    if is_stdio_mode:
        logging.getLogger("uvicorn").setLevel(logging.WARNING)
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        logging.getLogger("fastapi").setLevel(logging.WARNING)

    # Shared processors for all configurations
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    if settings.log_show_caller:
        shared_processors.append(structlog.processors.CallsiteParameterAdder())

    if settings.log_format == "json":
        # JSON logging for production
        processors = [
            *shared_processors,
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(serializer=orjson_serializer),
        ]
    else:
        # Console logging for development
        # Disable colors in STDIO mode to prevent ANSI escape codes
        use_colors = not is_stdio_mode
        processors = [
            *shared_processors,
            structlog.processors.dict_tracebacks,
            structlog.dev.ConsoleRenderer(colors=use_colors),
        ]

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Reduce noise from third-party libraries
    if is_stdio_mode:
        # Reduce noise in STDIO mode
        logging.getLogger("uvicorn").setLevel(logging.WARNING)
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        logging.getLogger("fastapi").setLevel(logging.WARNING)
        logging.getLogger("fastmcp").setLevel(logging.WARNING)
    else:
        logging.getLogger("uvicorn.access").setLevel(logging.INFO)
        logging.getLogger("httpx").setLevel(logging.INFO)

    return structlog.get_logger("litvar_link")


def orjson_serializer(obj: Any) -> str:
    """Fast JSON serializer using orjson."""
    try:
        import orjson

        return orjson.dumps(obj).decode("utf-8")
    except ImportError:
        import json

        return json.dumps(obj, default=str)


def log_api_request(
    logger: FilteringBoundLogger,
    method: str,
    url: str,
    response_time: float,
    status_code: int,
    error: str | None = None,
) -> None:
    """Log API request with structured data."""
    log_data = {
        "method": method,
        "url": url,
        "response_time_ms": round(response_time * 1000, 2),
        "status_code": status_code,
    }

    if error:
        log_data["error"] = error
        logger.error("API request failed", **log_data)
    else:
        logger.info("API request completed", **log_data)


def log_cache_operation(
    logger: FilteringBoundLogger,
    operation: str,
    key: str,
    hit: bool | None = None,
    size: int | None = None,
) -> None:
    """Log cache operation with structured data."""
    log_data = {
        "operation": operation,
        "key": key,
    }

    if hit is not None:
        log_data["cache_hit"] = hit
    if size is not None:
        log_data["cache_size"] = size

    logger.debug("Cache operation", **log_data)


def log_mcp_tool_call(
    logger: FilteringBoundLogger,
    tool_name: str,
    params: dict[str, Any],
    duration: float,
    success: bool,
    error: str | None = None,
) -> None:
    """Log MCP tool call with structured data."""
    log_data = {
        "tool_name": tool_name,
        "params": params,
        "duration_ms": round(duration * 1000, 2),
        "success": success,
    }

    if error:
        log_data["error"] = error
        logger.error("MCP tool call failed", **log_data)
    else:
        logger.info("MCP tool call completed", **log_data)


def log_server_startup(
    logger: FilteringBoundLogger,
    mode: str,
    host: str | None = None,
    port: int | None = None,
) -> None:
    """Log server startup with structured data."""
    log_data = {
        "mode": mode,
    }

    if host and port:
        log_data.update({"host": host, "port": port})

    logger.info("Server starting", **log_data)


def log_error_with_context(
    logger: FilteringBoundLogger,
    error: Exception,
    operation: str,
    context: dict[str, Any] | None = None,
) -> None:
    """Log error with additional context."""
    log_data = {
        "operation": operation,
        "error_type": type(error).__name__,
        "error_message": str(error),
    }

    if context:
        log_data["context"] = context

    logger.error("Operation failed", **log_data, exc_info=True)
