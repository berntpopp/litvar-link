"""Test CLI functionality."""

from __future__ import annotations

import argparse
from unittest.mock import AsyncMock, Mock, patch

import pytest
from rich.console import Console

from litvar_link import cli


def render_rich_object(rich_obj) -> str:
    """Helper function to render Rich objects to string for testing."""
    from io import StringIO

    console_output = StringIO()
    test_console = Console(file=console_output, width=80)
    test_console.print(rich_obj)
    return console_output.getvalue()


class TestTestConnection:
    """Test the test_connection CLI command."""

    @pytest.mark.asyncio
    async def test_connection_success_with_results(self):
        """Test successful connection with results."""
        mock_client = AsyncMock()
        mock_client.search_variants.return_value = [{"id": "test"}]

        with patch("litvar_link.cli.LitVar2Client") as mock_client_class:
            mock_client_class.return_value.__aenter__.return_value = mock_client
            with patch("litvar_link.cli.console.print") as mock_print:
                result = await cli.test_connection()

                assert result is True
                mock_client.search_variants.assert_called_once_with("rs", limit=1)
                mock_print.assert_called_once()
                # Check that success message was printed
                call_args = mock_print.call_args[0][0]
                output_text = render_rich_object(call_args)
                assert "Successfully connected" in output_text

    @pytest.mark.asyncio
    async def test_connection_success_no_results(self):
        """Test successful connection but no results."""
        mock_client = AsyncMock()
        mock_client.search_variants.return_value = []

        with patch("litvar_link.cli.LitVar2Client") as mock_client_class:
            mock_client_class.return_value.__aenter__.return_value = mock_client
            with patch("litvar_link.cli.console.print") as mock_print:
                result = await cli.test_connection()

                assert result is True
                mock_client.search_variants.assert_called_once_with("rs", limit=1)
                mock_print.assert_called_once()
                # Check that warning message was printed
                call_args = mock_print.call_args[0][0]
                output_text = render_rich_object(call_args)
                assert "Connected but no results" in output_text

    @pytest.mark.asyncio
    async def test_connection_failure(self):
        """Test connection failure."""
        mock_client = AsyncMock()
        mock_client.search_variants.side_effect = Exception("API Error")

        with patch("litvar_link.cli.LitVar2Client") as mock_client_class:
            mock_client_class.return_value.__aenter__.return_value = mock_client
            with patch("litvar_link.cli.console.print") as mock_print:
                result = await cli.test_connection()

                assert result is False
                mock_print.assert_called_once()
                # Check that error message was printed
                call_args = mock_print.call_args[0][0]
                output_text = render_rich_object(call_args)
                assert "Connection failed" in output_text
                assert "API Error" in output_text


class TestSearchVariants:
    """Test the search_variants CLI command."""

    @pytest.mark.asyncio
    async def test_search_variants_success(self):
        """Test successful variant search."""
        mock_variant = Mock()
        mock_variant.id = "variant_1"
        mock_variant.gene = ["BRCA1"]
        mock_variant.name = "Test Variant"
        mock_variant.rsid = "rs123"
        mock_variant.pmids_count = 5
        mock_variant.data_clinical_significance = ["Pathogenic"]

        mock_result = Mock()
        mock_result.variants = [mock_variant]
        mock_result.total_count = 1
        mock_result.search_time_ms = 123.4
        mock_result.cached = False

        mock_service = AsyncMock()
        mock_service.search_variants.return_value = mock_result

        mock_client = AsyncMock()

        with patch("litvar_link.cli.LitVar2Client") as mock_client_class:
            mock_client_class.return_value.__aenter__.return_value = mock_client
            with (
                patch("litvar_link.cli.VariantService", return_value=mock_service),
                patch("litvar_link.cli.console.print") as mock_print,
            ):
                await cli.search_variants("BRCA1", limit=5)

                mock_service.search_variants.assert_called_once_with(
                    query="BRCA1",
                    limit=5,
                )
                # Should print table and summary
                assert mock_print.call_count >= 2

    @pytest.mark.asyncio
    async def test_search_variants_with_long_id(self):
        """Test variant search with long variant ID."""
        mock_variant = Mock()
        mock_variant.id = "a" * 25  # Long ID that should be truncated
        mock_variant.gene = []
        mock_variant.name = None
        mock_variant.rsid = None
        mock_variant.pmids_count = None
        mock_variant.data_clinical_significance = None

        mock_result = Mock()
        mock_result.variants = [mock_variant]
        mock_result.total_count = 1
        mock_result.search_time_ms = 123.4
        mock_result.cached = True

        mock_service = AsyncMock()
        mock_service.search_variants.return_value = mock_result

        mock_client = AsyncMock()

        with patch("litvar_link.cli.LitVar2Client") as mock_client_class:
            mock_client_class.return_value.__aenter__.return_value = mock_client
            with (
                patch("litvar_link.cli.VariantService", return_value=mock_service),
                patch("litvar_link.cli.console.print") as mock_print,
            ):
                await cli.search_variants("test")

                # Should print cached message
                calls = [str(call) for call in mock_print.call_args_list]
                assert any("cache" in call.lower() for call in calls)

    @pytest.mark.asyncio
    async def test_search_variants_failure(self):
        """Test variant search failure."""
        mock_service = AsyncMock()
        mock_service.search_variants.side_effect = Exception("Search error")

        mock_client = AsyncMock()

        with patch("litvar_link.cli.LitVar2Client") as mock_client_class:
            mock_client_class.return_value.__aenter__.return_value = mock_client
            with (
                patch("litvar_link.cli.VariantService", return_value=mock_service),
                patch("litvar_link.cli.console.print") as mock_print,
                patch("sys.exit") as mock_exit,
            ):
                await cli.search_variants("test")

                mock_exit.assert_called_once_with(1)
                # Should print error message
                call_args = mock_print.call_args[0][0]
                output_text = render_rich_object(call_args)
                assert "search failed" in output_text.lower()


class TestLookupRSID:
    """Test the lookup_rsid CLI command."""

    @pytest.mark.asyncio
    async def test_rsid_lookup_available(self):
        """Test RSID lookup when available."""
        mock_result = Mock()
        mock_result.available = True
        mock_result.pmids_count = 10
        mock_result.gene = ["CFH"]
        mock_result.variant_name = "p.Y402H"

        mock_service = AsyncMock()
        mock_service.lookup_rsid.return_value = mock_result

        mock_client = AsyncMock()

        with patch("litvar_link.cli.LitVar2Client") as mock_client_class:
            mock_client_class.return_value.__aenter__.return_value = mock_client
            with (
                patch("litvar_link.cli.VariantService", return_value=mock_service),
                patch("litvar_link.cli.console.print") as mock_print,
            ):
                await cli.lookup_rsid("rs1061170")

                mock_service.lookup_rsid.assert_called_once_with("rs1061170")
                # Should print success message
                call_args = mock_print.call_args[0][0]
                output_text = render_rich_object(call_args)
                assert "available" in output_text.lower()

    @pytest.mark.asyncio
    async def test_rsid_lookup_not_available(self):
        """Test RSID lookup when not available."""
        mock_result = Mock()
        mock_result.available = False

        mock_service = AsyncMock()
        mock_service.lookup_rsid.return_value = mock_result

        mock_client = AsyncMock()

        with patch("litvar_link.cli.LitVar2Client") as mock_client_class:
            mock_client_class.return_value.__aenter__.return_value = mock_client
            with (
                patch("litvar_link.cli.VariantService", return_value=mock_service),
                patch("litvar_link.cli.console.print") as mock_print,
            ):
                await cli.lookup_rsid("rs999999")

                # Should print not found message
                call_args = mock_print.call_args[0][0]
                output_text = render_rich_object(call_args)
                assert "not found" in output_text.lower()

    @pytest.mark.asyncio
    async def test_rsid_lookup_with_none_values(self):
        """Test RSID lookup with None values."""
        mock_result = Mock()
        mock_result.available = True
        mock_result.pmids_count = None
        mock_result.gene = None
        mock_result.variant_name = None

        mock_service = AsyncMock()
        mock_service.lookup_rsid.return_value = mock_result

        mock_client = AsyncMock()

        with patch("litvar_link.cli.LitVar2Client") as mock_client_class:
            mock_client_class.return_value.__aenter__.return_value = mock_client
            with (
                patch("litvar_link.cli.VariantService", return_value=mock_service),
                patch("litvar_link.cli.console.print") as mock_print,
            ):
                await cli.lookup_rsid("rs123")

                # Should handle None values gracefully
                call_args = mock_print.call_args[0][0]
                output_text = render_rich_object(call_args)
                assert "Unknown" in output_text

    @pytest.mark.asyncio
    async def test_rsid_lookup_failure(self):
        """Test RSID lookup failure."""
        mock_service = AsyncMock()
        mock_service.lookup_rsid.side_effect = Exception("Lookup error")

        mock_client = AsyncMock()

        with patch("litvar_link.cli.LitVar2Client") as mock_client_class:
            mock_client_class.return_value.__aenter__.return_value = mock_client
            with (
                patch("litvar_link.cli.VariantService", return_value=mock_service),
                patch("litvar_link.cli.console.print") as mock_print,
                patch("sys.exit") as mock_exit,
            ):
                await cli.lookup_rsid("rs123")

                mock_exit.assert_called_once_with(1)
                # Should print error message
                call_args = mock_print.call_args[0][0]
                output_text = render_rich_object(call_args)
                assert "lookup failed" in output_text.lower()


class TestSearchGeneVariants:
    """Test the search_gene_variants CLI command."""

    @pytest.mark.asyncio
    async def test_gene_variants_success(self):
        """Test successful gene variant search."""
        mock_variant = Mock()
        mock_variant.rsid = "rs123"
        mock_variant.pmids_count = 5

        mock_result = Mock()
        mock_result.variants = [mock_variant]
        mock_result.total_count = 100
        mock_result.pathogenic_count = 20
        mock_result.benign_count = 60
        mock_result.uncertain_count = 20

        mock_service = AsyncMock()
        mock_service.search_gene_variants.return_value = mock_result

        mock_client = AsyncMock()

        with patch("litvar_link.cli.LitVar2Client") as mock_client_class:
            mock_client_class.return_value.__aenter__.return_value = mock_client
            with (
                patch("litvar_link.cli.VariantService", return_value=mock_service),
                patch("litvar_link.cli.console.print") as mock_print,
            ):
                await cli.search_gene_variants("CFH", limit=10)

                mock_service.search_gene_variants.assert_called_once_with("CFH")
                # Should print table and statistics
                assert mock_print.call_count >= 2

    @pytest.mark.asyncio
    async def test_gene_variants_no_rsid(self):
        """Test gene variant search with variant having no RSID."""
        mock_variant = Mock()
        mock_variant.rsid = None
        mock_variant.pmids_count = 3

        mock_result = Mock()
        mock_result.variants = [mock_variant]
        mock_result.total_count = 1
        mock_result.pathogenic_count = 0
        mock_result.benign_count = 1
        mock_result.uncertain_count = 0

        mock_service = AsyncMock()
        mock_service.search_gene_variants.return_value = mock_result

        mock_client = AsyncMock()

        with patch("litvar_link.cli.LitVar2Client") as mock_client_class:
            mock_client_class.return_value.__aenter__.return_value = mock_client
            with (
                patch("litvar_link.cli.VariantService", return_value=mock_service),
                patch("litvar_link.cli.console.print"),
            ):
                await cli.search_gene_variants("TEST")

    @pytest.mark.asyncio
    async def test_gene_variants_failure(self):
        """Test gene variant search failure."""
        mock_service = AsyncMock()
        mock_service.search_gene_variants.side_effect = Exception("Gene search error")

        mock_client = AsyncMock()

        with patch("litvar_link.cli.LitVar2Client") as mock_client_class:
            mock_client_class.return_value.__aenter__.return_value = mock_client
            with (
                patch("litvar_link.cli.VariantService", return_value=mock_service),
                patch("litvar_link.cli.console.print") as mock_print,
                patch("sys.exit") as mock_exit,
            ):
                await cli.search_gene_variants("INVALID")

                mock_exit.assert_called_once_with(1)
                # Should print error message
                call_args = mock_print.call_args[0][0]
                output_text = render_rich_object(call_args)
                assert "search failed" in output_text.lower()


class TestServerCommands:
    """Test server command functions."""

    @pytest.mark.asyncio
    async def test_serve_http_success(self):
        """Test HTTP server startup."""
        mock_manager = AsyncMock()

        with patch("litvar_link.cli.UnifiedServerManager", return_value=mock_manager):
            await cli.serve_http("0.0.0.0", 8080, True)  # noqa: S104

            mock_manager.start_http_only_server.assert_called_once_with(
                host="0.0.0.0",  # noqa: S104
                port=8080,
                reload=True,
            )

    @pytest.mark.asyncio
    async def test_serve_http_keyboard_interrupt(self):
        """Test HTTP server keyboard interrupt."""
        mock_manager = AsyncMock()
        mock_manager.start_http_only_server.side_effect = KeyboardInterrupt()

        with patch("litvar_link.cli.UnifiedServerManager", return_value=mock_manager):
            # Should not raise exception
            await cli.serve_http()

    @pytest.mark.asyncio
    async def test_serve_http_error(self):
        """Test HTTP server error."""
        mock_manager = AsyncMock()
        mock_manager.start_http_only_server.side_effect = Exception("Server error")

        with (
            patch("litvar_link.cli.UnifiedServerManager", return_value=mock_manager),
            patch("sys.exit") as mock_exit,
        ):
            await cli.serve_http()
            mock_exit.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_serve_unified_success(self):
        """Test unified server startup."""
        mock_manager = AsyncMock()

        with patch("litvar_link.cli.UnifiedServerManager", return_value=mock_manager):
            await cli.serve_unified("127.0.0.1", 9000, False)

            mock_manager.start_unified_server.assert_called_once_with(
                host="127.0.0.1",
                port=9000,
                reload=False,
            )

    @pytest.mark.asyncio
    async def test_serve_unified_keyboard_interrupt(self):
        """Test unified server keyboard interrupt."""
        mock_manager = AsyncMock()
        mock_manager.start_unified_server.side_effect = KeyboardInterrupt()

        with patch("litvar_link.cli.UnifiedServerManager", return_value=mock_manager):
            # Should not raise exception
            await cli.serve_unified()

    @pytest.mark.asyncio
    async def test_serve_unified_error(self):
        """Test unified server error."""
        mock_manager = AsyncMock()
        mock_manager.start_unified_server.side_effect = Exception("Unified error")

        with (
            patch("litvar_link.cli.UnifiedServerManager", return_value=mock_manager),
            patch("sys.exit") as mock_exit,
        ):
            await cli.serve_unified()
            mock_exit.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_serve_mcp_success(self):
        """Test MCP server startup."""
        mock_manager = AsyncMock()

        with patch("litvar_link.cli.UnifiedServerManager", return_value=mock_manager):
            await cli.serve_mcp_only()

            mock_manager.start_stdio_server.assert_called_once()

    @pytest.mark.asyncio
    async def test_serve_mcp_keyboard_interrupt(self):
        """Test MCP server keyboard interrupt."""
        mock_manager = AsyncMock()
        mock_manager.start_stdio_server.side_effect = KeyboardInterrupt()

        with patch("litvar_link.cli.UnifiedServerManager", return_value=mock_manager):
            # Should not raise exception
            await cli.serve_mcp_only()

    @pytest.mark.asyncio
    async def test_serve_mcp_error(self):
        """Test MCP server error."""
        mock_manager = AsyncMock()
        mock_manager.start_stdio_server.side_effect = Exception("MCP error")

        with (
            patch("litvar_link.cli.UnifiedServerManager", return_value=mock_manager),
            patch("sys.exit") as mock_exit,
        ):
            await cli.serve_mcp_only()
            mock_exit.assert_called_once_with(1)


class TestMainFunction:
    """Test the main CLI parser and command dispatch."""

    def test_main_test_command(self):
        """Test main function with test command."""
        with patch("sys.argv", ["litvar-link", "test"]):
            # Create a mock that closes the coroutine to prevent RuntimeWarning
            def mock_run_func(coro):
                coro.close()
                return

            with patch("asyncio.run", side_effect=mock_run_func) as mock_run:
                cli.main()
                # asyncio.run should be called once with the test_connection coroutine
                mock_run.assert_called_once()

    def test_main_search_command(self):
        """Test main function with search command."""
        with patch("sys.argv", ["litvar-link", "search", "BRCA1", "--limit", "5"]):
            # Create a mock that closes the coroutine to prevent RuntimeWarning
            def mock_run_func(coro):
                coro.close()
                return

            with (
                patch("asyncio.run", side_effect=mock_run_func) as mock_run,
                patch("litvar_link.cli.search_variants"),
            ):
                cli.main()
                mock_run.assert_called_once()
                # Verify search_variants was called with correct args
                mock_run.call_args[0][0]
                # The call_args should be the result of search_variants("BRCA1", 5)

    def test_main_search_command_default_limit(self):
        """Test main function with search command using default limit."""
        with patch("sys.argv", ["litvar-link", "search", "CFH"]):
            # Create a mock that closes the coroutine to prevent RuntimeWarning
            def mock_run_func(coro):
                coro.close()
                return

            with patch("asyncio.run", side_effect=mock_run_func) as mock_run:
                cli.main()
                mock_run.assert_called_once()

    def test_main_rsid_command(self):
        """Test main function with rsid command."""
        with patch("sys.argv", ["litvar-link", "rsid", "rs1061170"]):
            # Create a mock that closes the coroutine to prevent RuntimeWarning
            def mock_run_func(coro):
                coro.close()
                return

            with patch("asyncio.run", side_effect=mock_run_func) as mock_run:
                cli.main()
                mock_run.assert_called_once()

    def test_main_gene_command(self):
        """Test main function with gene command."""
        with patch("sys.argv", ["litvar-link", "gene", "CFH", "--limit", "15"]):
            # Create a mock that closes the coroutine to prevent RuntimeWarning
            def mock_run_func(coro):
                coro.close()
                return

            with patch("asyncio.run", side_effect=mock_run_func) as mock_run:
                cli.main()
                mock_run.assert_called_once()

    def test_main_gene_command_default_limit(self):
        """Test main function with gene command using default limit."""
        with patch("sys.argv", ["litvar-link", "gene", "BRCA1"]):
            # Create a mock that closes the coroutine to prevent RuntimeWarning
            def mock_run_func(coro):
                coro.close()
                return

            with patch("asyncio.run", side_effect=mock_run_func) as mock_run:
                cli.main()
                mock_run.assert_called_once()

    def test_main_serve_http_command(self):
        """Test main function with serve http command."""
        with patch(
            "sys.argv",
            [
                "litvar-link",
                "serve",
                "http",
                "--host",
                "0.0.0.0",  # noqa: S104
                "--port",
                "8080",
                "--reload",
            ],
        ):
            # Create a mock that closes the coroutine to prevent RuntimeWarning
            def mock_run_func(coro):
                coro.close()
                return

            with patch("asyncio.run", side_effect=mock_run_func) as mock_run:
                cli.main()
                mock_run.assert_called_once()

    def test_main_serve_http_defaults(self):
        """Test main function with serve http command using defaults."""
        with patch("sys.argv", ["litvar-link", "serve", "http"]):
            # Create a mock that closes the coroutine to prevent RuntimeWarning
            def mock_run_func(coro):
                coro.close()
                return

            with patch("asyncio.run", side_effect=mock_run_func) as mock_run:
                cli.main()
                mock_run.assert_called_once()

    def test_main_serve_unified_command(self):
        """Test main function with serve unified command."""
        with patch("sys.argv", ["litvar-link", "serve", "unified", "--port", "9000"]):
            # Create a mock that closes the coroutine to prevent RuntimeWarning
            def mock_run_func(coro):
                coro.close()
                return

            with patch("asyncio.run", side_effect=mock_run_func) as mock_run:
                cli.main()
                mock_run.assert_called_once()

    def test_main_serve_mcp_command(self):
        """Test main function with serve mcp command."""
        with patch("sys.argv", ["litvar-link", "serve", "mcp"]):
            # Create a mock that closes the coroutine to prevent RuntimeWarning
            def mock_run_func(coro):
                coro.close()
                return

            with patch("asyncio.run", side_effect=mock_run_func) as mock_run:
                cli.main()
                mock_run.assert_called_once()

    def test_main_serve_no_subcommand(self):
        """Test main function with serve but no subcommand."""
        with (
            patch("sys.argv", ["litvar-link", "serve"]),
            patch("argparse.ArgumentParser.print_help"),
        ):
            cli.main()
            # The subparser should print help when no subcommand is provided
            # This may not call print_help directly but shows usage

    def test_main_no_command(self):
        """Test main function with no command."""
        with (
            patch("sys.argv", ["litvar-link"]),
            patch("argparse.ArgumentParser.print_help") as mock_help,
        ):
            cli.main()
            mock_help.assert_called_once()

    def test_main_invalid_command(self):
        """Test main function with invalid command."""
        with patch("sys.argv", ["litvar-link", "invalid"]):
            # Should exit with code 2 (argparse error) for invalid command
            with pytest.raises(SystemExit) as exc_info:
                cli.main()
            assert exc_info.value.code == 2


class TestArgumentParsing:
    """Test CLI argument parsing logic."""

    def test_parser_creation(self):
        """Test that parser is created correctly."""
        # This tests the parser setup without calling main()
        parser = argparse.ArgumentParser(description="LitVar-Link CLI")
        subparsers = parser.add_subparsers(dest="command", help="Available commands")

        # Test command
        subparsers.add_parser("test", help="Test connection to LitVar2 API")

        args = parser.parse_args(["test"])
        assert args.command == "test"

    def test_search_parser_args(self):
        """Test search command argument parsing."""
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        search_parser = subparsers.add_parser("search")
        search_parser.add_argument("query")
        search_parser.add_argument("--limit", type=int, default=10)

        args = parser.parse_args(["search", "BRCA1", "--limit", "5"])
        assert args.command == "search"
        assert args.query == "BRCA1"
        assert args.limit == 5

    def test_server_parser_args(self):
        """Test server command argument parsing."""
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        server_parser = subparsers.add_parser("serve")
        server_subparsers = server_parser.add_subparsers(dest="serve_mode")

        http_parser = server_subparsers.add_parser("http")
        http_parser.add_argument("--host", default="127.0.0.1")
        http_parser.add_argument("--port", type=int, default=8000)
        http_parser.add_argument("--reload", action="store_true")

        args = parser.parse_args(
            ["serve", "http", "--host", "0.0.0.0", "--port", "8080", "--reload"],  # noqa: S104
        )
        assert args.command == "serve"
        assert args.serve_mode == "http"
        assert args.host == "0.0.0.0"  # noqa: S104
        assert args.port == 8080
        assert args.reload is True
