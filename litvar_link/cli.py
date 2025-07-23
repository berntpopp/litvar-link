"""Command-line interface for LitVar-Link."""

from __future__ import annotations

import argparse
import asyncio
import sys

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .api.client import LitVar2Client
from .config import get_api_config, get_cache_config
from .logging_config import configure_logging
from .server_manager import UnifiedServerManager
from .services.variant_service import VariantService

# Initialize rich console
console = Console()


async def test_connection() -> bool:
    """Test connection to LitVar2 API."""
    logger = configure_logging()

    with console.status("[bold blue]Testing LitVar2 API connection...", spinner="dots"):
        config = get_api_config()
        async with LitVar2Client(config=config, logger=logger) as client:
            try:
                # Test with a simple variant search
                result = await client.search_variants("rs", limit=1)

                if result:
                    console.print(
                        Panel(
                            f"[bold green]:white_check_mark: Successfully connected to LitVar2 API\n"  # noqa: E501
                            f"Found {len(result)} test result(s)",
                            title="Connection Test",
                            border_style="green",
                        ),
                    )
                    return True
                console.print(
                    Panel(
                        "[bold yellow]:warning: Connected but no results returned",
                        title="Connection Test",
                        border_style="yellow",
                    ),
                )
                return True

            except Exception as e:
                console.print(
                    Panel(
                        f"[bold red]:x: Connection failed: {e!s}",
                        title="Connection Test",
                        border_style="red",
                    ),
                )
                return False


async def search_variants(query: str, limit: int = 10) -> None:
    """Search for variants."""
    logger = configure_logging()

    search_desc = f"[bold blue]Searching for variants: '{query}'"

    with console.status(search_desc, spinner="dots"):
        config = get_api_config()
        async with LitVar2Client(config=config, logger=logger) as client:
            try:
                service = VariantService(client, get_cache_config(), logger)
                result = await service.search_variants(query=query, limit=limit)

                # Create a table for results
                table = Table(title=f"Variant Search Results for '{query}'")
                table.add_column("ID", style="cyan", no_wrap=True)
                table.add_column("Gene", style="green")
                table.add_column("Name", style="magenta")
                table.add_column("RSID", style="yellow")
                table.add_column("Publications", style="blue", justify="right")
                table.add_column("Clinical Significance", style="red")

                for variant in result.variants[:limit]:
                    clinical_sig = (
                        ", ".join(variant.data_clinical_significance)
                        if variant.data_clinical_significance
                        else "Unknown"
                    )

                    table.add_row(
                        variant.id[:20] + "..." if len(variant.id) > 20 else variant.id,
                        "/".join(variant.gene) if variant.gene else "N/A",
                        variant.name or "N/A",
                        variant.rsid or "N/A",
                        str(variant.pmids_count) if variant.pmids_count else "0",
                        clinical_sig,
                    )

                console.print(table)

                # Show summary
                console.print(
                    f"\n[bold]Summary:[/bold] Found {result.total_count} variant(s) "
                    f"in {result.search_time_ms:.1f}ms",
                )
                if result.cached:
                    console.print("[dim]Results served from cache[/dim]")

            except Exception as e:
                console.print(
                    Panel(
                        f"[bold red]:x: Variant search failed: {e!s}",
                        title="Search Error",
                        border_style="red",
                    ),
                )
                sys.exit(1)


async def lookup_rsid(rsid: str) -> None:
    """Look up RSID availability."""
    logger = configure_logging()

    with console.status(f"[bold blue]Looking up RSID: '{rsid}'", spinner="dots"):
        config = get_api_config()
        async with LitVar2Client(config=config, logger=logger) as client:
            try:
                service = VariantService(client, get_cache_config(), logger)
                result = await service.lookup_rsid(rsid)

                if result.available:
                    console.print(
                        Panel(
                            f"[bold green]:white_check_mark: RSID {rsid} is available in LitVar2\n"
                            f"Publications: {result.pmids_count or 'Unknown'}\n"
                            f"Gene: {'/'.join(result.gene) if result.gene else 'Unknown'}\n"
                            f"Variant: {result.variant_name or 'Unknown'}",
                            title="RSID Lookup",
                            border_style="green",
                        ),
                    )
                else:
                    console.print(
                        Panel(
                            f"[bold yellow]:warning: RSID {rsid} not found in LitVar2",
                            title="RSID Lookup",
                            border_style="yellow",
                        ),
                    )

            except Exception as e:
                console.print(
                    Panel(
                        f"[bold red]:x: RSID lookup failed: {e!s}",
                        title="Lookup Error",
                        border_style="red",
                    ),
                )
                sys.exit(1)


async def search_gene_variants(gene_name: str, limit: int = 20) -> None:
    """Search for variants in a gene."""
    logger = configure_logging()

    with console.status(
        f"[bold blue]Searching variants in gene: '{gene_name}'",
        spinner="dots",
    ):
        config = get_api_config()
        async with LitVar2Client(config=config, logger=logger) as client:
            try:
                service = VariantService(client, get_cache_config(), logger)
                result = await service.search_gene_variants(gene_name)

                # Create a table for results
                table = Table(title=f"Variants in Gene '{gene_name}'")
                table.add_column("Name", style="cyan")
                table.add_column("RSID", style="yellow")
                table.add_column("Publications", style="blue", justify="right")
                table.add_column("Clinical Significance", style="red")

                for variant in result.variants[:limit]:
                    # Gene variants endpoint doesn't include clinical significance or name  # noqa: E501
                    # Only has: _id, rsid (optional), pmids_count, and sometimes clingen_id  # noqa: E501
                    table.add_row(
                        "N/A",  # No name field in gene variants response
                        variant.rsid or "N/A",  # RSID is optional
                        str(variant.pmids_count),
                        "Unknown",  # No clinical significance in gene variants response
                    )

                console.print(table)

                # Show statistics
                console.print(
                    Panel(
                        f"[bold]Total Variants:[/bold] {result.total_count}\n"
                        f"[bold green]Pathogenic:[/bold green] {result.pathogenic_count}\n"
                        f"[bold blue]Benign:[/bold blue] {result.benign_count}\n"
                        f"[bold yellow]Uncertain:[/bold yellow] {result.uncertain_count}",
                        title="Gene Variant Statistics",
                        border_style="blue",
                    ),
                )

            except Exception as e:
                console.print(
                    Panel(
                        f"[bold red]:x: Gene variant search failed: {e!s}",
                        title="Search Error",
                        border_style="red",
                    ),
                )
                sys.exit(1)


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
        logger.error("Server error", error=str(e))
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
        logger.error("Server error", error=str(e))
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
        logger.error("MCP server error", error=str(e))
        sys.exit(1)


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="LitVar-Link CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Test connection command
    subparsers.add_parser("test", help="Test connection to LitVar2 API")

    # Server commands
    server_parser = subparsers.add_parser("serve", help="Start server")
    server_subparsers = server_parser.add_subparsers(
        dest="serve_mode",
        help="Server modes",
    )

    # HTTP server
    http_parser = server_subparsers.add_parser("http", help="Start HTTP-only server")
    http_parser.add_argument("--host", default="127.0.0.1", help="Server host")
    http_parser.add_argument("--port", type=int, default=8000, help="Server port")
    http_parser.add_argument("--reload", action="store_true", help="Enable auto-reload")

    # Unified server
    unified_parser = server_subparsers.add_parser(
        "unified",
        help="Start unified server (HTTP + MCP)",
    )
    unified_parser.add_argument("--host", default="127.0.0.1", help="Server host")
    unified_parser.add_argument("--port", type=int, default=8000, help="Server port")
    unified_parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload",
    )

    # MCP server
    server_subparsers.add_parser("mcp", help="Start MCP-only server")

    # Search commands
    search_parser = subparsers.add_parser("search", help="Search for variants")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("--limit", type=int, default=10, help="Maximum results")

    # RSID lookup command
    rsid_parser = subparsers.add_parser("rsid", help="Look up RSID availability")
    rsid_parser.add_argument("rsid", help="Reference SNP ID (e.g., rs1061170)")

    # Gene variants command
    gene_parser = subparsers.add_parser("gene", help="Search variants in a gene")
    gene_parser.add_argument("gene_name", help="Gene symbol (e.g., CFH)")
    gene_parser.add_argument("--limit", type=int, default=20, help="Maximum results")

    args = parser.parse_args()

    if args.command == "test":
        asyncio.run(test_connection())
    elif args.command == "search":
        asyncio.run(search_variants(args.query, args.limit))
    elif args.command == "rsid":
        asyncio.run(lookup_rsid(args.rsid))
    elif args.command == "gene":
        asyncio.run(search_gene_variants(args.gene_name, args.limit))
    elif args.command == "serve":
        if args.serve_mode == "http":
            asyncio.run(serve_http(args.host, args.port, args.reload))
        elif args.serve_mode == "unified":
            asyncio.run(serve_unified(args.host, args.port, args.reload))
        elif args.serve_mode == "mcp":
            asyncio.run(serve_mcp_only())
        else:
            server_parser.print_help()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
