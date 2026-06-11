"""Unified server management for different transport modes."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

import uvicorn

from .api.client import LitVar2Client
from .app import app
from .config import get_api_config, get_cache_config, settings
from .logging_config import log_server_startup
from .mcp.facade import create_litvar_mcp
from .services.variant_service import VariantService

if TYPE_CHECKING:
    from structlog.typing import FilteringBoundLogger


def _make_service_factory(
    logger: FilteringBoundLogger | None,
) -> Callable[[], VariantService]:
    """Build a per-call ``VariantService`` factory bound to a fresh client.

    The MCP tools call ``service_factory()`` lazily inside each tool body so each
    invocation gets a service over a freshly constructed ``LitVar2Client``.
    """

    def factory() -> VariantService:
        client = LitVar2Client(get_api_config(), logger)
        return VariantService(client, get_cache_config(), logger)

    return factory


class UnifiedServerManager:
    """Manages unified server with multiple transport protocols."""

    def __init__(self, logger: FilteringBoundLogger | None = None) -> None:
        """Initialize server manager.

        Args:
            logger: Optional logger instance
        """
        self.logger = logger

    async def start_unified_server(
        self,
        host: str = "127.0.0.1",
        port: int = 8000,
        reload: bool = False,
    ) -> None:
        """Start unified server (HTTP + MCP).

        Args:
            host: Server host
            port: Server port
            reload: Enable auto-reload
        """
        if self.logger:
            log_server_startup(self.logger, "unified", host, port)

        # Mount the explicit MCP facade as a stateless streamable-HTTP ASGI app.
        mcp = create_litvar_mcp(service_factory=_make_service_factory(self.logger))
        mcp_http_app = mcp.http_app(path="/", stateless_http=True, json_response=True)
        app.mount(settings.mcp_path, mcp_http_app)

        config = uvicorn.Config(
            app=app,
            host=host,
            port=port,
            reload=reload,
            log_config=None,  # Use our custom logging
            access_log=False,  # Disable uvicorn access log
        )

        server = uvicorn.Server(config)
        await server.serve()

    async def start_http_only_server(
        self,
        host: str = "127.0.0.1",
        port: int = 8000,
        reload: bool = False,
    ) -> None:
        """Start HTTP-only server.

        Args:
            host: Server host
            port: Server port
            reload: Enable auto-reload
        """
        if self.logger:
            log_server_startup(self.logger, "http", host, port)

        config = uvicorn.Config(
            app=app,
            host=host,
            port=port,
            reload=reload,
            log_config=None,  # Use our custom logging
            access_log=False,  # Disable uvicorn access log
        )

        server = uvicorn.Server(config)
        await server.serve()

    async def start_stdio_server(self) -> None:
        """Start STDIO MCP server (following pubtator-link pattern)."""
        if self.logger:
            log_server_startup(self.logger, "stdio")

        # Create FastAPI app so the shared lifespan (logging, etc.) runs.
        from .app import create_app, lifespan

        application = create_app()

        # Use lifespan context manager for consistency with HTTP mode
        if self.logger:
            self.logger.info("Initializing app state using lifespan context...")

        async with lifespan(application):
            # Build the explicit MCP facade within the lifespan context.
            mcp = create_litvar_mcp(service_factory=_make_service_factory(self.logger))

            if self.logger:
                self.logger.info("STDIO MCP server ready")

            # Run MCP server in STDIO mode
            await mcp.run_async(transport="stdio")
