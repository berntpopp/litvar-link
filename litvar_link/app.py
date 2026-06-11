"""Main FastAPI application."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title="LitVar-Link",
        description="High-performance MCP/API server for NCBI's LitVar2 genetic variant database",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=settings.cors_allow_methods,
        allow_headers=settings.cors_allow_headers,
    )

    # Include routers
    app.include_router(variants.router)
    app.include_router(publications.router)
    app.include_router(genes.router)
    app.include_router(sensor.router)
    app.include_router(health.router)

    from .api.error_handlers import register_exception_handlers

    register_exception_handlers(app)

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

    return app


# Create application instance
app = create_app()
