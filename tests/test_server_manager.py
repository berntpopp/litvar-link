"""Test server manager functionality."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
import uvicorn

from litvar_link.server_manager import UnifiedServerManager


class TestUnifiedServerManager:
    """Test UnifiedServerManager class."""

    def test_init_with_logger(self):
        """Test initialization with logger."""
        mock_logger = Mock()
        manager = UnifiedServerManager(logger=mock_logger)

        assert manager.logger is mock_logger

    def test_init_without_logger(self):
        """Test initialization without logger."""
        manager = UnifiedServerManager()

        assert manager.logger is None

    @pytest.mark.asyncio
    async def test_start_unified_server_with_defaults(self):
        """Test unified server startup with default parameters."""
        mock_logger = Mock()
        manager = UnifiedServerManager(logger=mock_logger)

        with patch("uvicorn.Server") as mock_server_class:
            mock_server = AsyncMock()
            mock_server_class.return_value = mock_server

            with patch("litvar_link.server_manager.log_server_startup") as mock_log:
                with patch("litvar_link.server_manager.app") as mock_app:
                    with patch("litvar_link.server_manager.mcp_app") as mock_mcp_app:
                        await manager.start_unified_server()

                        # Check logging
                        mock_log.assert_called_once_with(
                            mock_logger, "unified", "127.0.0.1", 8000
                        )

                        # Check MCP mount
                        mock_app.mount.assert_called_once()

                        # Check server creation and start
                        mock_server_class.assert_called_once()
                        config_arg = mock_server_class.call_args[0][0]
                        assert isinstance(config_arg, uvicorn.Config)
                        assert config_arg.host == "127.0.0.1"
                        assert config_arg.port == 8000
                        assert config_arg.reload is False
                        assert config_arg.log_config is None
                        assert config_arg.access_log is False

                        mock_server.serve.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_unified_server_with_custom_params(self):
        """Test unified server startup with custom parameters."""
        mock_logger = Mock()
        manager = UnifiedServerManager(logger=mock_logger)

        with patch("uvicorn.Server") as mock_server_class:
            mock_server = AsyncMock()
            mock_server_class.return_value = mock_server

            with patch("litvar_link.server_manager.log_server_startup") as mock_log:
                with patch("litvar_link.server_manager.app"):
                    with patch("litvar_link.server_manager.mcp_app"):
                        await manager.start_unified_server(
                            host="0.0.0.0", port=9000, reload=True
                        )

                        # Check logging with custom params
                        mock_log.assert_called_once_with(
                            mock_logger, "unified", "0.0.0.0", 9000
                        )

                        # Check server config
                        config_arg = mock_server_class.call_args[0][0]
                        assert config_arg.host == "0.0.0.0"
                        assert config_arg.port == 9000
                        assert config_arg.reload is True

    @pytest.mark.asyncio
    async def test_start_unified_server_without_logger(self):
        """Test unified server startup without logger."""
        manager = UnifiedServerManager()

        with patch("uvicorn.Server") as mock_server_class:
            mock_server = AsyncMock()
            mock_server_class.return_value = mock_server

            with patch("litvar_link.server_manager.log_server_startup") as mock_log:
                with patch("litvar_link.server_manager.app"):
                    with patch("litvar_link.server_manager.mcp_app"):
                        await manager.start_unified_server()

                        # Should not call logging
                        mock_log.assert_not_called()

    @pytest.mark.asyncio
    async def test_start_http_only_server_with_defaults(self):
        """Test HTTP-only server startup with default parameters."""
        mock_logger = Mock()
        manager = UnifiedServerManager(logger=mock_logger)

        with patch("uvicorn.Server") as mock_server_class:
            mock_server = AsyncMock()
            mock_server_class.return_value = mock_server

            with patch("litvar_link.server_manager.log_server_startup") as mock_log:
                with patch("litvar_link.server_manager.app") as mock_app:
                    await manager.start_http_only_server()

                    # Check logging
                    mock_log.assert_called_once_with(
                        mock_logger, "http", "127.0.0.1", 8000
                    )

                    # Should NOT mount MCP
                    mock_app.mount.assert_not_called()

                    # Check server creation and start
                    mock_server_class.assert_called_once()
                    config_arg = mock_server_class.call_args[0][0]
                    assert isinstance(config_arg, uvicorn.Config)
                    assert config_arg.host == "127.0.0.1"
                    assert config_arg.port == 8000
                    assert config_arg.reload is False

                    mock_server.serve.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_http_only_server_with_custom_params(self):
        """Test HTTP-only server startup with custom parameters."""
        mock_logger = Mock()
        manager = UnifiedServerManager(logger=mock_logger)

        with patch("uvicorn.Server") as mock_server_class:
            mock_server = AsyncMock()
            mock_server_class.return_value = mock_server

            with patch("litvar_link.server_manager.log_server_startup") as mock_log:
                with patch("litvar_link.server_manager.app"):
                    await manager.start_http_only_server(
                        host="192.168.1.100", port=8080, reload=True
                    )

                    # Check logging with custom params
                    mock_log.assert_called_once_with(
                        mock_logger, "http", "192.168.1.100", 8080
                    )

                    # Check server config
                    config_arg = mock_server_class.call_args[0][0]
                    assert config_arg.host == "192.168.1.100"
                    assert config_arg.port == 8080
                    assert config_arg.reload is True

    @pytest.mark.asyncio
    async def test_start_http_only_server_without_logger(self):
        """Test HTTP-only server startup without logger."""
        manager = UnifiedServerManager()

        with patch("uvicorn.Server") as mock_server_class:
            mock_server = AsyncMock()
            mock_server_class.return_value = mock_server

            with patch("litvar_link.server_manager.log_server_startup") as mock_log:
                with patch("litvar_link.server_manager.app"):
                    await manager.start_http_only_server()

                    # Should not call logging
                    mock_log.assert_not_called()

    @pytest.mark.asyncio
    async def test_start_stdio_server_with_logger(self):
        """Test STDIO server startup with logger."""
        mock_logger = Mock()
        manager = UnifiedServerManager(logger=mock_logger)

        # Mock the app creation functions
        mock_app = Mock()
        mock_mcp = AsyncMock()
        mock_lifespan = AsyncMock()

        with patch("litvar_link.server_manager.log_server_startup") as mock_log:
            with patch("litvar_link.app.create_app", return_value=mock_app):
                with patch("litvar_link.app.create_mcp_app", return_value=mock_mcp):
                    with patch("litvar_link.app.lifespan", return_value=mock_lifespan):
                        # Make the async context manager work
                        mock_lifespan.__aenter__ = AsyncMock(return_value=None)
                        mock_lifespan.__aexit__ = AsyncMock(return_value=None)

                        await manager.start_stdio_server()

                        # Check logging calls
                        mock_log.assert_called_once_with(mock_logger, "stdio")
                        assert mock_logger.info.call_count >= 2

                        # Check MCP server run
                        mock_mcp.run_async.assert_called_once_with(transport="stdio")

    @pytest.mark.asyncio
    async def test_start_stdio_server_without_logger(self):
        """Test STDIO server startup without logger."""
        manager = UnifiedServerManager()

        # Mock the app creation functions
        mock_app = Mock()
        mock_mcp = AsyncMock()
        mock_lifespan = AsyncMock()

        with patch("litvar_link.server_manager.log_server_startup") as mock_log:
            with patch("litvar_link.app.create_app", return_value=mock_app):
                with patch("litvar_link.app.create_mcp_app", return_value=mock_mcp):
                    with patch("litvar_link.app.lifespan", return_value=mock_lifespan):
                        # Make the async context manager work
                        mock_lifespan.__aenter__ = AsyncMock(return_value=None)
                        mock_lifespan.__aexit__ = AsyncMock(return_value=None)

                        await manager.start_stdio_server()

                        # Should not call logging
                        mock_log.assert_not_called()

                        # Check MCP server still runs
                        mock_mcp.run_async.assert_called_once_with(transport="stdio")

    @pytest.mark.asyncio
    async def test_start_stdio_server_logs_initialization(self):
        """Test STDIO server logs initialization steps."""
        mock_logger = Mock()
        manager = UnifiedServerManager(logger=mock_logger)

        # Mock the app creation functions
        mock_app = Mock()
        mock_mcp = AsyncMock()
        mock_lifespan = AsyncMock()

        with patch("litvar_link.server_manager.log_server_startup"):
            with patch("litvar_link.app.create_app", return_value=mock_app):
                with patch("litvar_link.app.create_mcp_app", return_value=mock_mcp):
                    with patch("litvar_link.app.lifespan", return_value=mock_lifespan):
                        # Make the async context manager work
                        mock_lifespan.__aenter__ = AsyncMock(return_value=None)
                        mock_lifespan.__aexit__ = AsyncMock(return_value=None)

                        await manager.start_stdio_server()

                        # Check that info messages were logged
                        info_calls = [call for call in mock_logger.info.call_args_list]
                        assert len(info_calls) >= 2

                        # Check specific log messages
                        log_messages = [str(call) for call in info_calls]
                        assert any("lifespan context" in msg for msg in log_messages)
                        assert any(
                            "STDIO MCP server ready" in msg for msg in log_messages
                        )

    @pytest.mark.asyncio
    async def test_uvicorn_config_properties(self):
        """Test that uvicorn.Config is created with correct properties."""
        manager = UnifiedServerManager()

        with patch("uvicorn.Server") as mock_server_class:
            mock_server = AsyncMock()
            mock_server_class.return_value = mock_server

            with patch("litvar_link.server_manager.app") as mock_app:
                await manager.start_http_only_server(
                    host="test.local", port=3000, reload=True
                )

                # Extract the config that was passed to uvicorn.Server
                config_arg = mock_server_class.call_args[0][0]

                # Verify all config properties
                assert config_arg.app is mock_app
                assert config_arg.host == "test.local"
                assert config_arg.port == 3000
                assert config_arg.reload is True
                assert config_arg.log_config is None
                assert config_arg.access_log is False

    @pytest.mark.asyncio
    async def test_app_mounting_in_unified_mode(self):
        """Test that MCP app is properly mounted in unified mode."""
        manager = UnifiedServerManager()

        with patch("uvicorn.Server") as mock_server_class:
            mock_server = AsyncMock()
            mock_server_class.return_value = mock_server

            with patch("litvar_link.server_manager.app") as mock_app:
                with patch("litvar_link.server_manager.mcp_app") as mock_mcp_app:
                    with patch("litvar_link.server_manager.settings") as mock_settings:
                        mock_settings.mcp_path = "/mcp"

                        await manager.start_unified_server()

                        # Verify MCP app was mounted at the correct path
                        mock_app.mount.assert_called_once_with(
                            "/mcp", mock_mcp_app.mcp_router
                        )
