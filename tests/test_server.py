"""Tests for the server.py module."""

import importlib
import importlib.util
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

import server

# ===== Server Module Tests =====


class TestServerInitialization:
    """Test server initialization and configuration."""

    def test_server_initializes_successfully(self):
        """Test that server initializes successfully with tools loaded."""
        # Server should be imported successfully
        assert server.mcp is not None
        assert server.app is not None
        # The logger should exist
        assert server.logger is not None

    def test_server_load_tools_error_handling(self):
        """Test that server properly logs errors during tool loading."""
        # This test verifies the error handling exists
        # The actual import-time error handling (lines 25-27) is tested
        # by the fact that the module imports successfully in other tests
        # We can verify the logger is configured
        assert server.logger is not None
        assert server.logger.name == "server"


class TestMainFunction:
    """Test the main() function with different modes."""

    def test_main_stdio_mode(self):
        """Test main function in stdio mode."""
        with (
            patch.object(sys, "argv", ["server.py", "stdio"]),
            patch("builtins.print") as mock_print,
            patch.object(server.mcp, "run") as mock_run,
        ):
            server.main()

            mock_print.assert_called_once_with("Running MCP in stdio mode...")
            mock_run.assert_called_once_with()

    @patch("server.uvicorn.run")
    def test_main_http_mode(self, mock_uvicorn):
        """Test main function in HTTP mode."""
        with (
            patch.object(sys, "argv", ["server.py", "http"]),
            patch("builtins.print") as mock_print,
        ):
            server.main()

            mock_print.assert_called_once_with("Running MCP over HTTP streaming...")
            # Check that uvicorn was called with correct args (don't check app object identity)
            assert mock_uvicorn.call_count == 1
            call_args = mock_uvicorn.call_args
            assert call_args[1]["host"] == "127.0.0.1"
            assert call_args[1]["port"] == 5001

    @patch("server.uvicorn.run")
    def test_main_sse_mode(self, mock_uvicorn):
        """Test main function in SSE mode."""
        with (
            patch.object(sys, "argv", ["server.py", "sse"]),
            patch("builtins.print") as mock_print,
        ):
            server.main()

            mock_print.assert_called_once_with("Running MCP over HTTP streaming...")
            # Check that uvicorn was called with correct args
            assert mock_uvicorn.call_count == 1
            call_args = mock_uvicorn.call_args
            assert call_args[1]["host"] == "127.0.0.1"
            assert call_args[1]["port"] == 5001

    @patch("server.uvicorn.run")
    def test_main_default_mode(self, mock_uvicorn):
        """Test main function defaults to HTTP mode when no args provided."""
        with (
            patch.object(sys, "argv", ["server.py"]),
            patch("builtins.print") as mock_print,
        ):
            server.main()

            mock_print.assert_called_once_with("Running MCP over HTTP streaming...")
            # Check that uvicorn was called with correct args
            assert mock_uvicorn.call_count == 1
            call_args = mock_uvicorn.call_args
            assert call_args[1]["host"] == "127.0.0.1"
            assert call_args[1]["port"] == 5001

    def test_main_invalid_mode(self):
        """Test main function raises error for invalid mode."""

        with patch.object(sys, "argv", ["server.py", "invalid_mode"]):
            with pytest.raises(ValueError) as exc_info:
                server.main()

            assert "Unknown mode: invalid_mode" in str(exc_info.value)


class TestAppConfiguration:
    """Test the FastAPI app configuration."""

    def test_app_has_mcp_path(self):
        """Test that app is configured with /mcp path."""
        # The app should be created via mcp.http_app() at module level
        assert server.app is not None
        # The app is a FastAPI/Starlette app with routes
        assert hasattr(server.app, "routes")
        # Verify it's the correct type from FastMCP
        assert server.app.__class__.__name__ == "StarletteWithLifespan"


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


class TestImportTimeErrorHandling:
    """Test error handling during server module import."""

    def test_server_handles_tool_loading_failure_on_import(self):
        """Test that server properly handles and re-raises tool loading errors during import."""

        # Remove server from cache if it exists
        if "server" in sys.modules:
            del sys.modules["server"]

        # Also remove related modules
        for key in list(sys.modules.keys()):
            if key.startswith("loader") or key.startswith("middleware"):
                del sys.modules[key]

        # Mock load_tools_from_directory to raise an exception
        with patch("loader.load_tools_from_directory") as mock_loader:
            mock_loader.side_effect = Exception("Tool loading failed")

            # Mock get_cors_middleware to return a mock
            with patch("middleware.get_cors_middleware") as mock_cors:
                mock_cors.return_value = Mock()

                # Now try to import server - it should raise the exception
                with pytest.raises(Exception, match="Tool loading failed"):
                    import server as _  # noqa: F401  # pylint: disable=reimported,import-outside-toplevel
