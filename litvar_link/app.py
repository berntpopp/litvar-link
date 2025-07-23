"""Main FastAPI application with FastMCP integration."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastmcp import FastMCP
from fastmcp.server.openapi import MCPType, RouteMap

from .api.routes import genes, health, publications, sensor, variants
from .config import settings
from .logging_config import configure_logging, log_server_startup


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

    # Root endpoint
    @app.get("/")
    async def root() -> dict[str, Any]:
        """Root endpoint with service information."""
        return {
            "name": "LitVar-Link",
            "version": "0.1.0",
            "description": "High-performance MCP/API server for NCBI's LitVar2 genetic variant database",  # noqa: E501
            "docs": "/docs",
            "health": "/api/health",
            "mcp_endpoint": settings.mcp_path,
        }

    return app


def create_mcp_app() -> FastMCP:
    """Create FastMCP server from FastAPI app."""
    app = create_app()

    # MCP tool name mappings (following pubtator-link pattern)
    mcp_custom_names = {
        "search_variants": "search_genetic_variants",
        "get_variant_details": "get_variant_summary",
        "get_variant_publications": "get_variant_literature",
        "lookup_rsid": "lookup_rsid_availability",
        "get_gene_variants": "search_gene_variants",
    }

    # Route mappings for MCP tools (exclude utility endpoints)
    mcp_route_maps = [
        # Exclude health and monitoring endpoints
        RouteMap(pattern=r"^/api/health.*$", mcp_type=MCPType.EXCLUDE),
        # Exclude root and docs endpoints
        RouteMap(pattern=r"^/$", mcp_type=MCPType.EXCLUDE),
        RouteMap(pattern=r"^/docs$", mcp_type=MCPType.EXCLUDE),
        RouteMap(pattern=r"^/openapi.json$", mcp_type=MCPType.EXCLUDE),
        RouteMap(pattern=r"^/redoc$", mcp_type=MCPType.EXCLUDE),
    ]

    # Create FastMCP instance
    mcp = FastMCP.from_fastapi(
        app=app,
        name="LitVar-Link Server",
        mcp_names=mcp_custom_names,
        route_maps=mcp_route_maps,
    )

    return mcp


# Create application instances
app = create_app()
mcp_app = create_mcp_app()
