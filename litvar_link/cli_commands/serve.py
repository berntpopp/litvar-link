"""Serve commands: http, unified, mcp (stdio).

The async helpers carry the verbatim behaviour from the original argparse
``cli.py`` serve functions. They are mounted as a typer sub-app under ``serve``
so the invocation paths (``serve http|unified|mcp`` with ``--host``/``--port``/
``--reload``) and exit codes survive the argparse -> typer migration. The
Makefile ``dev``/``mcp-serve-http`` targets call ``serve unified --host ...
--port ...``; that path is preserved here unchanged.
"""

from __future__ import annotations

import asyncio
import sys

import typer

from litvar_link.logging_config import configure_logging
from litvar_link.server_manager import UnifiedServerManager

serve_app = typer.Typer(help="Start the server in a transport mode.")


async def serve_http(
    host: str = "127.0.0.1",
    port: int = 8000,
    reload: bool = False,
) -> None:
    """Start HTTP-only server."""
    logger = configure_logging()
    manager = UnifiedServerManager(logger=logger)

    try:
        logger.info("Starting HTTP server", host=host, port=port, reload=reload)
        await manager.start_http_only_server(host=host, port=port, reload=reload)
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.exception("Server error", error=str(e))
        sys.exit(1)


async def serve_unified(
    host: str = "127.0.0.1",
    port: int = 8000,
    reload: bool = False,
) -> None:
    """Start unified server (HTTP + MCP)."""
    logger = configure_logging()
    manager = UnifiedServerManager(logger=logger)

    try:
        logger.info("Starting unified server", host=host, port=port, reload=reload)
        await manager.start_unified_server(host=host, port=port, reload=reload)
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.exception("Server error", error=str(e))
        sys.exit(1)


async def serve_mcp_only() -> None:
    """Start MCP-only server."""
    logger = configure_logging()
    manager = UnifiedServerManager(logger=logger)

    try:
        logger.info("Starting MCP server")
        await manager.start_stdio_server()
    except KeyboardInterrupt:
        logger.info("MCP server stopped by user")
    except Exception as e:
        logger.exception("MCP server error", error=str(e))
        sys.exit(1)


@serve_app.command("http")
def http(
    host: str = typer.Option("127.0.0.1", "--host", help="Server host"),
    port: int = typer.Option(8000, "--port", help="Server port"),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload"),
) -> None:
    """Start the HTTP-only server."""
    asyncio.run(serve_http(host, port, reload))


@serve_app.command("unified")
def unified(
    host: str = typer.Option("127.0.0.1", "--host", help="Server host"),
    port: int = typer.Option(8000, "--port", help="Server port"),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload"),
) -> None:
    """Start the unified server (HTTP + MCP)."""
    asyncio.run(serve_unified(host, port, reload))


@serve_app.command("mcp")
def mcp() -> None:
    """Start the stdio MCP server."""
    asyncio.run(serve_mcp_only())


def register(app: typer.Typer) -> None:
    """Mount the serve sub-app under ``serve``."""
    app.add_typer(serve_app, name="serve")
