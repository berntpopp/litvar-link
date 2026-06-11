"""Test CLI command behaviour (typer app + cli_commands helpers).

The async command bodies live in ``litvar_link.cli_commands.{data,serve}`` after
the argparse -> typer migration. These tests exercise those verbatim helper
bodies directly (behavioural contract) plus the typer dispatch wiring in
``litvar_link.cli`` (each command resolves to the right helper with the right
args). The command/flag surface itself is pinned by ``tests/unit/test_cli.py``.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest
from rich.console import Console
from typer.testing import CliRunner

from litvar_link import cli
from litvar_link.cli_commands import data, serve

runner = CliRunner()


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

        with patch("litvar_link.cli_commands.data.LitVar2Client") as mock_client_class:
            mock_client_class.return_value.__aenter__.return_value = mock_client
            with patch("litvar_link.cli_commands.data.console.print") as mock_print:
                result = await data.test_connection()

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

        with patch("litvar_link.cli_commands.data.LitVar2Client") as mock_client_class:
            mock_client_class.return_value.__aenter__.return_value = mock_client
            with patch("litvar_link.cli_commands.data.console.print") as mock_print:
                result = await data.test_connection()

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

        with patch("litvar_link.cli_commands.data.LitVar2Client") as mock_client_class:
            mock_client_class.return_value.__aenter__.return_value = mock_client
            with patch("litvar_link.cli_commands.data.console.print") as mock_print:
                result = await data.test_connection()

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

        with patch("litvar_link.cli_commands.data.LitVar2Client") as mock_client_class:
            mock_client_class.return_value.__aenter__.return_value = mock_client
            with (
                patch("litvar_link.cli_commands.data.VariantService", return_value=mock_service),
                patch("litvar_link.cli_commands.data.console.print") as mock_print,
            ):
                await data.search_variants("BRCA1", limit=5)

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

        with patch("litvar_link.cli_commands.data.LitVar2Client") as mock_client_class:
            mock_client_class.return_value.__aenter__.return_value = mock_client
            with (
                patch("litvar_link.cli_commands.data.VariantService", return_value=mock_service),
                patch("litvar_link.cli_commands.data.console.print") as mock_print,
            ):
                await data.search_variants("test")

                # Should print cached message
                calls = [str(call) for call in mock_print.call_args_list]
                assert any("cache" in call.lower() for call in calls)

    @pytest.mark.asyncio
    async def test_search_variants_failure(self):
        """Test variant search failure."""
        mock_service = AsyncMock()
        mock_service.search_variants.side_effect = Exception("Search error")

        mock_client = AsyncMock()

        with patch("litvar_link.cli_commands.data.LitVar2Client") as mock_client_class:
            mock_client_class.return_value.__aenter__.return_value = mock_client
            with (
                patch("litvar_link.cli_commands.data.VariantService", return_value=mock_service),
                patch("litvar_link.cli_commands.data.console.print") as mock_print,
                patch("sys.exit") as mock_exit,
            ):
                await data.search_variants("test")

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

        with patch("litvar_link.cli_commands.data.LitVar2Client") as mock_client_class:
            mock_client_class.return_value.__aenter__.return_value = mock_client
            with (
                patch("litvar_link.cli_commands.data.VariantService", return_value=mock_service),
                patch("litvar_link.cli_commands.data.console.print") as mock_print,
            ):
                await data.lookup_rsid("rs1061170")

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

        with patch("litvar_link.cli_commands.data.LitVar2Client") as mock_client_class:
            mock_client_class.return_value.__aenter__.return_value = mock_client
            with (
                patch("litvar_link.cli_commands.data.VariantService", return_value=mock_service),
                patch("litvar_link.cli_commands.data.console.print") as mock_print,
            ):
                await data.lookup_rsid("rs999999")

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

        with patch("litvar_link.cli_commands.data.LitVar2Client") as mock_client_class:
            mock_client_class.return_value.__aenter__.return_value = mock_client
            with (
                patch("litvar_link.cli_commands.data.VariantService", return_value=mock_service),
                patch("litvar_link.cli_commands.data.console.print") as mock_print,
            ):
                await data.lookup_rsid("rs123")

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

        with patch("litvar_link.cli_commands.data.LitVar2Client") as mock_client_class:
            mock_client_class.return_value.__aenter__.return_value = mock_client
            with (
                patch("litvar_link.cli_commands.data.VariantService", return_value=mock_service),
                patch("litvar_link.cli_commands.data.console.print") as mock_print,
                patch("sys.exit") as mock_exit,
            ):
                await data.lookup_rsid("rs123")

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

        with patch("litvar_link.cli_commands.data.LitVar2Client") as mock_client_class:
            mock_client_class.return_value.__aenter__.return_value = mock_client
            with (
                patch("litvar_link.cli_commands.data.VariantService", return_value=mock_service),
                patch("litvar_link.cli_commands.data.console.print") as mock_print,
            ):
                await data.search_gene_variants("CFH", limit=10)

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

        with patch("litvar_link.cli_commands.data.LitVar2Client") as mock_client_class:
            mock_client_class.return_value.__aenter__.return_value = mock_client
            with (
                patch("litvar_link.cli_commands.data.VariantService", return_value=mock_service),
                patch("litvar_link.cli_commands.data.console.print"),
            ):
                await data.search_gene_variants("TEST")

    @pytest.mark.asyncio
    async def test_gene_variants_failure(self):
        """Test gene variant search failure."""
        mock_service = AsyncMock()
        mock_service.search_gene_variants.side_effect = Exception("Gene search error")

        mock_client = AsyncMock()

        with patch("litvar_link.cli_commands.data.LitVar2Client") as mock_client_class:
            mock_client_class.return_value.__aenter__.return_value = mock_client
            with (
                patch("litvar_link.cli_commands.data.VariantService", return_value=mock_service),
                patch("litvar_link.cli_commands.data.console.print") as mock_print,
                patch("sys.exit") as mock_exit,
            ):
                await data.search_gene_variants("INVALID")

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

        with patch(
            "litvar_link.cli_commands.serve.UnifiedServerManager",
            return_value=mock_manager,
        ):
            await serve.serve_http("0.0.0.0", 8080, True)  # noqa: S104

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

        with patch(
            "litvar_link.cli_commands.serve.UnifiedServerManager",
            return_value=mock_manager,
        ):
            # Should not raise exception
            await serve.serve_http()

    @pytest.mark.asyncio
    async def test_serve_http_error(self):
        """Test HTTP server error."""
        mock_manager = AsyncMock()
        mock_manager.start_http_only_server.side_effect = Exception("Server error")

        with (
            patch(
                "litvar_link.cli_commands.serve.UnifiedServerManager",
                return_value=mock_manager,
            ),
            patch("sys.exit") as mock_exit,
        ):
            await serve.serve_http()
            mock_exit.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_serve_unified_success(self):
        """Test unified server startup."""
        mock_manager = AsyncMock()

        with patch(
            "litvar_link.cli_commands.serve.UnifiedServerManager",
            return_value=mock_manager,
        ):
            await serve.serve_unified("127.0.0.1", 9000, False)

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

        with patch(
            "litvar_link.cli_commands.serve.UnifiedServerManager",
            return_value=mock_manager,
        ):
            # Should not raise exception
            await serve.serve_unified()

    @pytest.mark.asyncio
    async def test_serve_unified_error(self):
        """Test unified server error."""
        mock_manager = AsyncMock()
        mock_manager.start_unified_server.side_effect = Exception("Unified error")

        with (
            patch(
                "litvar_link.cli_commands.serve.UnifiedServerManager",
                return_value=mock_manager,
            ),
            patch("sys.exit") as mock_exit,
        ):
            await serve.serve_unified()
            mock_exit.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_serve_mcp_success(self):
        """Test MCP server startup."""
        mock_manager = AsyncMock()

        with patch(
            "litvar_link.cli_commands.serve.UnifiedServerManager",
            return_value=mock_manager,
        ):
            await serve.serve_mcp_only()

            mock_manager.start_stdio_server.assert_called_once()

    @pytest.mark.asyncio
    async def test_serve_mcp_keyboard_interrupt(self):
        """Test MCP server keyboard interrupt."""
        mock_manager = AsyncMock()
        mock_manager.start_stdio_server.side_effect = KeyboardInterrupt()

        with patch(
            "litvar_link.cli_commands.serve.UnifiedServerManager",
            return_value=mock_manager,
        ):
            # Should not raise exception
            await serve.serve_mcp_only()

    @pytest.mark.asyncio
    async def test_serve_mcp_error(self):
        """Test MCP server error."""
        mock_manager = AsyncMock()
        mock_manager.start_stdio_server.side_effect = Exception("MCP error")

        with (
            patch(
                "litvar_link.cli_commands.serve.UnifiedServerManager",
                return_value=mock_manager,
            ),
            patch("sys.exit") as mock_exit,
        ):
            await serve.serve_mcp_only()
            mock_exit.assert_called_once_with(1)


class TestTyperDispatch:
    """Test the typer app dispatches each command to the right helper.

    Replaces the old argparse ``TestMainFunction``/``TestArgumentParsing``
    classes: same dispatch contract (command -> coroutine), expressed through
    the typer ``CliRunner`` instead of ``sys.argv`` + ``argparse``.
    """

    def _swallow(self, coro) -> None:
        """Close a coroutine without awaiting to avoid RuntimeWarning."""
        coro.close()

    def test_dispatch_test_command(self):
        """`test` runs the connection-test helper."""
        with (
            patch("asyncio.run", side_effect=self._swallow) as mock_run,
            patch.object(data, "test_connection") as mock_fn,
        ):
            result = runner.invoke(cli.app, ["test"])
            assert result.exit_code == 0
            mock_run.assert_called_once()
            mock_fn.assert_called_once_with()

    def test_dispatch_search_command(self):
        """`search QUERY --limit N` calls search_variants(QUERY, N)."""
        with (
            patch("asyncio.run", side_effect=self._swallow) as mock_run,
            patch.object(data, "search_variants") as mock_fn,
        ):
            result = runner.invoke(cli.app, ["search", "BRCA1", "--limit", "5"])
            assert result.exit_code == 0
            mock_run.assert_called_once()
            mock_fn.assert_called_once_with("BRCA1", 5)

    def test_dispatch_search_command_default_limit(self):
        """`search QUERY` uses the default limit of 10."""
        with (
            patch("asyncio.run", side_effect=self._swallow),
            patch.object(data, "search_variants") as mock_fn,
        ):
            result = runner.invoke(cli.app, ["search", "CFH"])
            assert result.exit_code == 0
            mock_fn.assert_called_once_with("CFH", 10)

    def test_dispatch_rsid_command(self):
        """`rsid RS` calls lookup_rsid(RS)."""
        with (
            patch("asyncio.run", side_effect=self._swallow),
            patch.object(data, "lookup_rsid") as mock_fn,
        ):
            result = runner.invoke(cli.app, ["rsid", "rs1061170"])
            assert result.exit_code == 0
            mock_fn.assert_called_once_with("rs1061170")

    def test_dispatch_gene_command(self):
        """`gene GENE --limit N` calls search_gene_variants(GENE, N)."""
        with (
            patch("asyncio.run", side_effect=self._swallow),
            patch.object(data, "search_gene_variants") as mock_fn,
        ):
            result = runner.invoke(cli.app, ["gene", "CFH", "--limit", "15"])
            assert result.exit_code == 0
            mock_fn.assert_called_once_with("CFH", 15)

    def test_dispatch_gene_command_default_limit(self):
        """`gene GENE` uses the default limit of 20."""
        with (
            patch("asyncio.run", side_effect=self._swallow),
            patch.object(data, "search_gene_variants") as mock_fn,
        ):
            result = runner.invoke(cli.app, ["gene", "BRCA1"])
            assert result.exit_code == 0
            mock_fn.assert_called_once_with("BRCA1", 20)

    def test_dispatch_serve_http_command(self):
        """`serve http --host H --port P --reload` calls serve_http(H, P, True)."""
        with (
            patch("asyncio.run", side_effect=self._swallow),
            patch.object(serve, "serve_http") as mock_fn,
        ):
            result = runner.invoke(
                cli.app,
                ["serve", "http", "--host", "0.0.0.0", "--port", "8080", "--reload"],  # noqa: S104
            )
            assert result.exit_code == 0
            mock_fn.assert_called_once_with("0.0.0.0", 8080, True)  # noqa: S104

    def test_dispatch_serve_http_defaults(self):
        """`serve http` uses the documented defaults."""
        with (
            patch("asyncio.run", side_effect=self._swallow),
            patch.object(serve, "serve_http") as mock_fn,
        ):
            result = runner.invoke(cli.app, ["serve", "http"])
            assert result.exit_code == 0
            mock_fn.assert_called_once_with("127.0.0.1", 8000, False)

    def test_dispatch_serve_unified_command(self):
        """`serve unified --port P` calls serve_unified with that port."""
        with (
            patch("asyncio.run", side_effect=self._swallow),
            patch.object(serve, "serve_unified") as mock_fn,
        ):
            result = runner.invoke(cli.app, ["serve", "unified", "--port", "9000"])
            assert result.exit_code == 0
            mock_fn.assert_called_once_with("127.0.0.1", 9000, False)

    def test_dispatch_serve_mcp_command(self):
        """`serve mcp` calls serve_mcp_only with no args."""
        with (
            patch("asyncio.run", side_effect=self._swallow),
            patch.object(serve, "serve_mcp_only") as mock_fn,
        ):
            result = runner.invoke(cli.app, ["serve", "mcp"])
            assert result.exit_code == 0
            mock_fn.assert_called_once_with()

    def test_dispatch_no_command_shows_help(self):
        """Invoking with no command shows help text (no_args_is_help).

        typer's ``no_args_is_help`` shows the command list and exits non-zero
        (2), whereas the old argparse ``main()`` printed help and exited 0. The
        meaningful contract preserved here is "no command -> help is shown".
        """
        result = runner.invoke(cli.app, [])
        assert "Commands" in result.stdout

    def test_dispatch_invalid_command_exits_nonzero(self):
        """An unknown command exits non-zero."""
        result = runner.invoke(cli.app, ["invalid"])
        assert result.exit_code != 0

    def test_main_invokes_app(self):
        """`main()` invokes the typer app (console-script / python -m path)."""
        with patch.object(cli, "app") as mock_app:
            cli.main()
            mock_app.assert_called_once_with()
