"""Data commands: test, search, rsid, gene.

The async helpers below carry the verbatim behaviour from the original
argparse ``cli.py`` (connection test + the three service-backed lookups). The
``register`` function wires thin typer command wrappers onto the shared app so
the scripting contract (``test``/``search``/``rsid``/``gene`` with the same
flags and exit codes) is preserved across the argparse -> typer migration.
"""

from __future__ import annotations

import asyncio
import sys

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from litvar_link.api.client import LitVar2Client
from litvar_link.config import get_api_config, get_cache_config
from litvar_link.logging_config import configure_logging
from litvar_link.services.variant_service import VariantService

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
                            f"[bold green]:white_check_mark: Successfully connected to LitVar2 API\n"
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
                    # Gene variants endpoint doesn't include clinical significance or name
                    # Only has: _id, rsid (optional), pmids_count, and sometimes clingen_id
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


def register(app: typer.Typer) -> None:
    """Register the data commands (test, search, rsid, gene) on the typer app."""

    @app.command()
    def test() -> None:
        """Test connection to the LitVar2 API."""
        asyncio.run(test_connection())

    @app.command()
    def search(
        query: str = typer.Argument(..., help="Search query"),
        limit: int = typer.Option(10, "--limit", help="Maximum results"),
    ) -> None:
        """Search for variants."""
        asyncio.run(search_variants(query, limit))

    @app.command()
    def rsid(
        rsid: str = typer.Argument(..., help="Reference SNP ID, e.g. rs1061170"),
    ) -> None:
        """Look up RSID availability."""
        asyncio.run(lookup_rsid(rsid))

    @app.command()
    def gene(
        gene_name: str = typer.Argument(..., help="Gene symbol, e.g. CFH"),
        limit: int = typer.Option(20, "--limit", help="Maximum results"),
    ) -> None:
        """Search variants in a gene."""
        asyncio.run(search_gene_variants(gene_name, limit))
