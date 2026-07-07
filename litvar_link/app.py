"""Main FastAPI application."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from litvar_link import __version__

from .api.routes import genes, health, publications, sensor, variants
from .config import settings
from .logging_config import configure_logging, log_server_startup

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    logger = configure_logging()
    log_server_startup(logger, "startup", settings.host, settings.port)

    yield

    logger.info("Application shutting down")


def _configure_app(app: FastAPI) -> None:
    """Attach CORS middleware, API routers, and exception handlers to ``app``."""
    # This backend is unauthenticated (no cookies/session), so CORS credentials
    # are meaningless — they default OFF (see config.cors_allow_credentials).
    # Fail closed if an operator re-enables them alongside a wildcard origin:
    # the browser rejects `Access-Control-Allow-Credentials: true` paired with
    # `*`, and doing so would let any site issue credentialed cross-origin
    # requests. Refuse to start rather than silently downgrade.
    if settings.cors_allow_credentials and "*" in settings.cors_origins:
        raise RuntimeError(
            "CORS misconfiguration: cors_allow_credentials=True is incompatible "
            "with a wildcard '*' origin. This backend is unauthenticated and "
            "needs no credentials; set cors_allow_credentials=False."
        )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=settings.cors_allow_methods,
        allow_headers=settings.cors_allow_headers,
    )

    app.include_router(variants.router)
    app.include_router(publications.router)
    app.include_router(genes.router)
    app.include_router(sensor.router)
    app.include_router(health.router)

    from .api.error_handlers import register_exception_handlers

    register_exception_handlers(app)


def create_app(extra_lifespan: Any = None) -> FastAPI:
    """Create and configure FastAPI application.

    Args:
        extra_lifespan: Optional additional ASGI lifespan context manager to run
            alongside the app's own lifespan. The unified server passes the MCP
            streamable-HTTP app's ``lifespan`` here so FastMCP's session-manager
            task group is initialized (mounting the MCP app is not enough; its
            lifespan must run on the parent app, per FastMCP's ASGI docs).
    """
    if extra_lifespan is None:
        app_lifespan = lifespan
    else:

        @asynccontextmanager
        async def app_lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
            async with lifespan(app), extra_lifespan(app):
                yield

    app = FastAPI(
        title="LitVar-Link",
        description="High-performance MCP/API server for NCBI's LitVar2 genetic variant database",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=app_lifespan,
    )

    _configure_app(app)

    # Root endpoint
    @app.get("/")
    async def root() -> dict[str, Any]:
        """Root endpoint with service information."""
        return {
            "name": "LitVar-Link",
            "version": "0.1.0",
            "description": "High-performance MCP/API server for NCBI's LitVar2 genetic variant database",
            "docs": "/docs",
            "health": "/api/health",
            "mcp_endpoint": settings.mcp_path,
        }

    # Lightweight health endpoint required by MCP Transport Standard v1.
    # Returns the mandatory {status, version, transport} triple without any
    # external I/O so it can be used as a readiness probe for the container.
    @app.get("/health")
    async def health_v1() -> dict[str, Any]:
        """MCP Transport Standard v1 health probe."""
        return {
            "status": "ok",
            "version": __version__,
            "transport": "streamable-http-stateless",
        }

    return app


# Create application instance
app = create_app()
