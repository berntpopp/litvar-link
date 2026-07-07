"""Structured logging configuration for LitVar-Link."""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING, Any, cast
from urllib.parse import urlsplit

import structlog

from .config import settings

if TYPE_CHECKING:
    from structlog.typing import FilteringBoundLogger, Processor


def _detect_stdio_mode() -> bool:
    """Return True when running under the MCP/STDIO transport."""
    import os

    return (
        os.environ.get("TRANSPORT") == "stdio"
        or getattr(settings, "transport_mode", None) == "stdio"
    )


def _build_processors(*, is_stdio_mode: bool) -> list[Processor]:
    """Assemble the structlog processor chain for the active log format."""
    shared_processors: list[Processor] = [
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
        return [
            *shared_processors,
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(serializer=orjson_serializer),
        ]
    # Console logging for development; disable colors in STDIO mode (ANSI-safe).
    return [
        *shared_processors,
        structlog.processors.dict_tracebacks,
        structlog.dev.ConsoleRenderer(colors=not is_stdio_mode),
    ]


def _quiet_third_party_loggers(*, is_stdio_mode: bool) -> None:
    """Reduce noise from HTTP/server libraries per transport mode."""
    if is_stdio_mode:
        for name in ("uvicorn", "httpx", "httpcore", "fastapi", "fastmcp"):
            logging.getLogger(name).setLevel(logging.WARNING)
    else:
        logging.getLogger("uvicorn.access").setLevel(logging.INFO)
        logging.getLogger("httpx").setLevel(logging.INFO)


def configure_logging() -> FilteringBoundLogger:
    """Configure structured logging with structlog."""
    is_stdio_mode = _detect_stdio_mode()

    # For MCP/STDIO mode, use stderr to avoid interfering with the JSON protocol;
    # for HTTP mode, use stdout for normal logging.
    log_stream = sys.stderr if is_stdio_mode else sys.stdout
    logging.basicConfig(
        format="%(message)s",
        stream=log_stream,
        level=getattr(logging, settings.log_level),
    )

    structlog.configure(
        processors=_build_processors(is_stdio_mode=is_stdio_mode),
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    _quiet_third_party_loggers(is_stdio_mode=is_stdio_mode)

    return cast("FilteringBoundLogger", structlog.get_logger("litvar_link"))


def orjson_serializer(obj: Any, *, default: Any = None, **_kwargs: Any) -> str:
    """Fast JSON serializer using orjson.

    structlog's ``JSONRenderer`` calls the serializer with a ``default``
    callable (the fallback used for values that are not natively JSON
    serializable) plus other keyword args; accept and forward ``default`` and
    tolerate the rest so structured logging works under LOG_FORMAT=json.
    """
    try:
        import orjson

        if default is not None:
            return orjson.dumps(obj, default=default).decode("utf-8")
        return orjson.dumps(obj).decode("utf-8")
    except ImportError:
        import json

        return json.dumps(obj, default=default or str)


def _redact_url(url: str) -> str:
    """Reduce a URL to ``scheme://host[:port]``, dropping path/query/fragment.

    LitVar2 request URLs embed patient-adjacent identifiers -- rsIDs, HGVS, gene
    symbols, canonical variant ids -- in their *path* (e.g.
    ``/variant/get/litvar@rs113993960##``). Logging the full URL therefore leaks
    those identifiers to the log sink (finding M3). Only the host is retained so
    logs still say *which* upstream was contacted without disclosing *what* was
    looked up. A URL that does not parse degrades to a constant placeholder
    rather than echoing the raw (possibly identifier-bearing) string.
    """
    try:
        parts = urlsplit(url)
    except ValueError:
        return "<unparseable-url>"
    if parts.scheme and parts.netloc:
        return f"{parts.scheme}://{parts.netloc}"
    return parts.netloc or "<redacted-url>"


def log_api_request(
    logger: FilteringBoundLogger,
    method: str,
    url: str,
    response_time: float,
    status_code: int,
    error: str | None = None,
) -> None:
    """Log API request with structured data.

    PII-safe (finding M3): the full ``url`` and any raw ``error`` string are
    NEVER logged -- both can carry variant/rsid/gene identifiers (in the path,
    or in a wrapped message like ``Request timeout: <url>``). Only the host,
    method, status, and timing are emitted; ``error`` merely selects the log
    level. The signature is kept stable for existing callers.
    """
    log_data: dict[str, Any] = {
        "method": method,
        "host": _redact_url(url),
        "response_time_ms": round(response_time * 1000, 2),
        "status_code": status_code,
    }

    if error:
        logger.error("API request failed", **log_data)
    else:
        logger.info("API request completed", **log_data)


def log_cache_operation(
    logger: FilteringBoundLogger,
    operation: str,
    namespace: str,
    hit: bool | None = None,
    size: int | None = None,
) -> None:
    """Log cache operation with structured data.

    PII-safe (finding M3): ``namespace`` MUST be a non-sensitive cache namespace
    or clear pattern (e.g. ``search_variants``, ``all``) -- never a raw cache
    key built from call arguments, which on LitVar routes carry variant/rsid/
    gene identifiers. Only the namespace, operation, hit, and size are emitted.
    """
    log_data: dict[str, Any] = {
        "operation": operation,
        "cache_namespace": namespace,
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
    """Log MCP tool call with structured data.

    PII-safe (finding M3): raw ``params`` *values* (query/rsid/gene/variant) and
    any raw ``error`` string are NEVER logged. Only the sorted param *key* names
    are emitted (field names are not sensitive), alongside tool/timing/success;
    ``error`` merely selects the log level. Signature kept stable for callers.
    """
    log_data: dict[str, Any] = {
        "tool_name": tool_name,
        "param_keys": sorted(params) if params else [],
        "duration_ms": round(duration * 1000, 2),
        "success": success,
    }

    if error:
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
    log_data: dict[str, Any] = {
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
    """Log error with additional context.

    PII-safe (finding M3): neither the ``error_message`` (``str(error)`` can
    embed a variant/rsid/url -- e.g. ``No LitVar2 variant found for '<rsid>'``)
    nor the raw ``context`` *values* (query/variant_id/rsid/gene_name/url/pmid)
    are logged. Only the operation, the exception *type*, and the sorted context
    *key* names are emitted.

    ``exc_info`` is deliberately NOT passed: the production JSON renderer
    expands it into a traceback whose ``exc_value`` re-embeds the exception
    message (and thus the identifier) into the rendered log record, defeating
    the field-level redaction above. Callers needing a full traceback for a
    non-sensitive error should log it explicitly at the call site.
    Signature kept stable for callers.
    """
    log_data: dict[str, Any] = {
        "operation": operation,
        "error_type": type(error).__name__,
    }

    if context:
        log_data["context_keys"] = sorted(context)

    logger.error("Operation failed", **log_data)
