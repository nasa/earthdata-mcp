"""Tests for the server.py module."""

import pytest
import sys
import subprocess
import importlib
import importlib.util
from pathlib import Path
from unittest.mock import Mock, patch, call
import server

# ===== Server Module Tests =====


class TestServerInitialization:
    """Test server initialization and configuration."""

    @patch("loader.load_tools_from_directory")
    @patch("middleware.cors.get_cors_middleware")
    def test_server_handles_loader_failure_at_module_level(
        self, mock_cors, mock_loader
    ):
        """Test that server raises exception when tool loading fails during import."""
        mock_cors.return_value = Mock()
        mock_loader.side_effect = Exception("Failed to load tools")

        with pytest.raises(Exception) as exc_info:

            # Remove from cache if exists
            if "server" in sys.modules:
                del sys.modules["server"]

            # This should raise during import

        assert "Failed to load tools" in str(exc_info.value)


class TestMainFunction:
    """Test the main() function with different modes."""

    @patch("server.mcp")
    def test_main_stdio_mode(self, mock_mcp):
        """Test main function in stdio mode."""

        with patch.object(sys, "argv", ["server.py", "stdio"]):
            with patch("builtins.print") as mock_print:
                server.main()

                mock_print.assert_called_once_with("Running MCP in stdio mode...")
                mock_mcp.run.assert_called_once()

    @patch("server.uvicorn.run")
    @patch("server.app")
    def test_main_http_mode(self, mock_app, mock_uvicorn):
        """Test main function in HTTP mode."""

        with patch.object(sys, "argv", ["server.py", "http"]):
            with patch("builtins.print") as mock_print:
                server.main()

                mock_print.assert_called_once_with("Running MCP over HTTP streaming...")
                mock_uvicorn.assert_called_once_with(
                    mock_app, host="127.0.0.1", port=5001
                )

    @patch("server.uvicorn.run")
    @patch("server.app")
    def test_main_sse_mode(self, mock_app, mock_uvicorn):
        """Test main function in SSE mode."""

        with patch.object(sys, "argv", ["server.py", "sse"]):
            with patch("builtins.print") as mock_print:
                server.main()

                mock_print.assert_called_once_with("Running MCP over HTTP streaming...")
                mock_uvicorn.assert_called_once_with(
                    mock_app, host="127.0.0.1", port=5001
                )

    @patch("server.uvicorn.run")
    @patch("server.app")
    def test_main_default_mode(self, mock_app, mock_uvicorn):
        """Test main function defaults to HTTP mode when no args provided."""

        with patch.object(sys, "argv", ["server.py"]):
            with patch("builtins.print") as mock_print:
                server.main()

                mock_print.assert_called_once_with("Running MCP over HTTP streaming...")
                mock_uvicorn.assert_called_once_with(
                    mock_app, host="127.0.0.1", port=5001
                )

    def test_main_invalid_mode(self):
        """Test main function raises error for invalid mode."""

        with patch.object(sys, "argv", ["server.py", "invalid_mode"]):
            with pytest.raises(ValueError) as exc_info:
                server.main()

            assert "Unknown mode: invalid_mode" in str(exc_info.value)


class TestAppConfiguration:
    """Test the FastAPI app configuration."""

    @patch("server.load_tools_from_directory")
    @patch("server.get_cors_middleware")
    def test_app_has_mcp_path(self, mock_cors, mock_loader):
        """Test that app is configured with /mcp path."""
        mock_cors.return_value = Mock()
        mock_loader.return_value = {"loaded": [], "failed": []}

        importlib.reload(server)

        # The app should be created via mcp.http_app()
        assert server.app is not None


class TestMainEntryPoint:
    """Test the if __name__ == '__main__' entry point."""

    def test_server_main_block_execution(self):
        """Test that the if __name__ == '__main__' block executes correctly."""
        # Get the path to server.py
        server_path = Path("server.py").resolve()

        # Mock the dependencies that would block
        with (
            patch("uvicorn.run") as mock_uvicorn,
            patch("builtins.print") as mock_print,
            patch.object(sys, "argv", ["server.py", "http"]),
        ):

            # Load the module as __main__
            spec = importlib.util.spec_from_file_location("__main__", server_path)
            module = importlib.util.module_from_spec(spec)

            # Add to sys.modules so imports work
            sys.modules["__main__"] = module

            try:
                # Execute the module (this will run the if __name__ == "__main__" block)
                spec.loader.exec_module(module)
            except SystemExit:
                pass
            finally:
                # Clean up
                if "__main__" in sys.modules and sys.modules["__main__"] == module:
                    del sys.modules["__main__"]

            # Verify that main() was called (which calls uvicorn.run)
            assert mock_uvicorn.called, "main() should have been executed"
            mock_print.assert_any_call("Running MCP over HTTP streaming...")
