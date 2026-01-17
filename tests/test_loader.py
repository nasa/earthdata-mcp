"""Tests for the loader.py module."""

import json
from unittest.mock import Mock, patch

import pytest

from loader import ToolManifest, create_simple_tool, load_tools_from_directory


class TestToolManifest:
    """Test cases for ToolManifest class."""

    def test_manifest_with_valid_file(self, tmp_path):
        """Test loading a valid manifest.json file."""
        manifest_data = {
            "name": "test_tool",
            "description": "A test tool",
            "tags": ["test", "example"],
        }
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest_data))

        manifest = ToolManifest(tmp_path)

        assert manifest.name == "test_tool"
        assert manifest.description == "A test tool"
        assert manifest.tags == ["test", "example"]

    def test_manifest_without_file(self, tmp_path, capsys):
        """Test behavior when manifest.json doesn't exist."""
        manifest = ToolManifest(tmp_path)

        assert manifest.name == "unnamed_tool"
        assert manifest.description == "No description provided."
        assert manifest.tags == []

        captured = capsys.readouterr()
        assert "No manifest.json found" in captured.out

    def test_manifest_with_invalid_json(self, tmp_path, capsys):
        """Test behavior when manifest.json contains invalid JSON."""
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text("{invalid json}")

        manifest = ToolManifest(tmp_path)

        assert manifest.name == "unnamed_tool"
        assert manifest.description == "No description provided."

        captured = capsys.readouterr()
        assert "Could not read manifest.json" in captured.out

    def test_manifest_get_method(self, tmp_path):
        """Test the get method of ToolManifest."""
        manifest_data = {"name": "test_tool", "custom_field": "custom_value"}
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest_data))

        manifest = ToolManifest(tmp_path)

        assert manifest.get("name") == "test_tool"
        assert manifest.get("custom_field") == "custom_value"
        assert manifest.get("nonexistent", "default") == "default"


class TestCreateSimpleTool:
    """Test cases for create_simple_tool function."""

    def test_create_simple_tool_basic(self, tmp_path):
        """Test creating a simple tool with basic configuration."""
        manifest_data = {"name": "test_tool", "description": "A test tool"}
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest_data))

        def tool_func(keyword: str) -> dict:
            return {"result": f"Processed {keyword}"}

        register_func = create_simple_tool(tmp_path, tool_func)

        # Mock MCP object
        mock_mcp = Mock()
        mock_tool_decorator = Mock(return_value=lambda f: f)
        mock_mcp.tool = mock_tool_decorator

        register_func(mock_mcp)

        # Verify tool was registered with correct parameters
        mock_mcp.tool.assert_called_once()
        call_kwargs = mock_mcp.tool.call_args[1]
        assert call_kwargs["name"] == "test_tool"
        assert call_kwargs["description"] == "A test tool"
        assert call_kwargs["output_schema"] is None

    def test_create_simple_tool_with_output_schema(self, tmp_path):
        """Test creating a tool with output schema."""
        manifest_data = {"name": "test_tool", "description": "Test"}
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest_data))

        def tool_func(keyword: str) -> dict:
            return {"result": keyword}

        output_schema = {"type": "object", "properties": {"result": {"type": "string"}}}
        register_func = create_simple_tool(tmp_path, tool_func, output_schema)

        mock_mcp = Mock()
        mock_tool_decorator = Mock(return_value=lambda f: f)
        mock_mcp.tool = mock_tool_decorator

        register_func(mock_mcp)

        call_kwargs = mock_mcp.tool.call_args[1]
        assert call_kwargs["output_schema"] == output_schema

    @pytest.mark.asyncio
    async def test_create_simple_tool_wrapper_execution(self, tmp_path):
        """Test that the wrapper function executes and returns results correctly."""
        manifest_data = {"name": "test_tool", "description": "Test"}
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest_data))

        def tool_func(keyword: str) -> dict:
            return {"result": f"Processed {keyword}"}

        register_func = create_simple_tool(tmp_path, tool_func)

        # Capture the wrapper function
        wrapper_func = None

        def mock_tool_decorator(**_kwargs):
            def decorator(func):
                nonlocal wrapper_func
                wrapper_func = func
                return func

            return decorator

        mock_mcp = Mock()
        mock_mcp.tool = mock_tool_decorator

        register_func(mock_mcp)

        # Now call the wrapper to cover lines 84-85
        # pylint: disable=not-callable
        result = await wrapper_func(keyword="test")
        assert result == {"result": "Processed test"}


class TestLoadToolsFromDirectory:
    """Test cases for load_tools_from_directory function."""

    @patch("loader.importlib.import_module")
    def test_load_tools_success(self, mock_import, tmp_path, capsys):
        """Test successfully loading tools from directory."""
        tools_dir = tmp_path / "tools"
        tools_dir.mkdir()

        # Create a valid tool
        tool_dir = tools_dir / "test_tool"
        tool_dir.mkdir()

        manifest = {
            "name": "test_tool",
            "description": "Test tool",
            "entry_function": "register",
        }
        (tool_dir / "manifest.json").write_text(json.dumps(manifest))

        # Mock the tool module with a register function
        mock_tool_module = Mock()

        def mock_register(param: str) -> dict:
            return {"result": param}

        mock_tool_module.register = mock_register

        # Setup: loader imports tool.py successfully, output_model.py fails (doesn't exist)
        mock_import.side_effect = [
            mock_tool_module,  # First call: tools.test_tool.tool
            ImportError("No module named 'tools.test_tool.output_model'"),  # Second call
        ]

        mock_mcp = Mock()
        mock_mcp.tool = Mock(return_value=lambda f: f)

        result = load_tools_from_directory(mock_mcp, str(tools_dir))

        assert "test_tool" in result["loaded"]
        assert len(result["failed"]) == 0
        # Verify the tool module was imported
        assert mock_import.call_count == 2
        mock_import.assert_any_call("tools.test_tool.tool")

        captured = capsys.readouterr()
        assert "✓ test_tool" in captured.out

    def test_load_tools_skip_hidden_dirs(self, tmp_path):
        """Test that hidden directories are skipped."""
        tools_dir = tmp_path / "tools"
        tools_dir.mkdir()

        # Create hidden directory
        hidden_dir = tools_dir / ".hidden"
        hidden_dir.mkdir()
        (hidden_dir / "manifest.json").write_text(json.dumps({"name": "hidden"}))

        mock_mcp = Mock()
        result = load_tools_from_directory(mock_mcp, str(tools_dir))

        assert len(result["loaded"]) == 0
        assert len(result["failed"]) == 0

    def test_load_tools_missing_manifest(self, tmp_path, capsys):
        """Test behavior when tool directory has no manifest.json."""
        tools_dir = tmp_path / "tools"
        tools_dir.mkdir()

        tool_dir = tools_dir / "no_manifest_tool"
        tool_dir.mkdir()

        mock_mcp = Mock()
        result = load_tools_from_directory(mock_mcp, str(tools_dir))

        captured = capsys.readouterr()
        assert "[SKIP] no_manifest_tool: No manifest.json" in captured.out
        assert len(result["loaded"]) == 0

    @patch("loader.importlib.import_module")
    def test_load_tools_missing_entry_function(self, mock_import, tmp_path, capsys):
        """Test behavior when tool module is missing entry function."""
        tools_dir = tmp_path / "tools"
        tools_dir.mkdir()

        tool_dir = tools_dir / "broken_tool"
        tool_dir.mkdir()

        manifest = {"name": "broken_tool", "entry_function": "register"}
        (tool_dir / "manifest.json").write_text(json.dumps(manifest))

        # Mock module without the register function
        mock_module = Mock(spec=[])
        mock_import.return_value = mock_module

        mock_mcp = Mock()
        result = load_tools_from_directory(mock_mcp, str(tools_dir))

        assert "broken_tool" in result["failed"]
        captured = capsys.readouterr()
        assert "✗ broken_tool" in captured.out

    @patch("loader.importlib.import_module")
    def test_load_tools_with_output_schema(self, mock_import, tmp_path, capsys):
        """Test loading tool with JSON output schema."""
        tools_dir = tmp_path / "tools"
        tools_dir.mkdir()

        tool_dir = tools_dir / "schema_tool"
        tool_dir.mkdir()

        manifest = {"name": "schema_tool", "entry_function": "register"}
        (tool_dir / "manifest.json").write_text(json.dumps(manifest))

        output_schema = {"type": "object"}
        (tool_dir / "output.json").write_text(json.dumps(output_schema))

        # Mock the tool module with a register function
        mock_tool_module = Mock()

        def mock_register(param: str) -> dict:
            return {"result": param}

        mock_tool_module.register = mock_register

        # Setup: tool.py imports successfully, output_model.py doesn't exist
        mock_import.side_effect = [
            mock_tool_module,  # First call: tools.schema_tool.tool
            ImportError("No module"),  # Second call: tools.schema_tool.output_model (doesn't exist)
        ]

        mock_mcp = Mock()
        mock_mcp.tool = Mock(return_value=lambda f: f)

        result = load_tools_from_directory(mock_mcp, str(tools_dir))

        assert "schema_tool" in result["loaded"]
        captured = capsys.readouterr()
        # This should hit line 159 - the JSON schema loading print statement
        assert "Using JSON schema for schema_tool" in captured.out

    @patch("loader.importlib.import_module")
    def test_load_tools_missing_name_field(self, mock_import, tmp_path, capsys):
        """Test behavior when manifest.json is missing the 'name' field."""
        tools_dir = tmp_path / "tools"
        tools_dir.mkdir()

        tool_dir = tools_dir / "no_name_tool"
        tool_dir.mkdir()

        # Manifest without 'name' field
        manifest = {"description": "Tool without name", "entry_function": "register"}
        (tool_dir / "manifest.json").write_text(json.dumps(manifest))

        mock_mcp = Mock()
        result = load_tools_from_directory(mock_mcp, str(tools_dir))

        assert "no_name_tool" in result["failed"]
        captured = capsys.readouterr()
        assert "✗ no_name_tool" in captured.out
        assert "missing 'name' field" in captured.out
        mock_import.assert_not_called()

    @patch("loader.importlib.import_module")
    def test_load_tools_invalid_output_schema(self, mock_import, tmp_path, capsys):
        """Test behavior when output.json contains invalid JSON."""
        tools_dir = tmp_path / "tools"
        tools_dir.mkdir()

        tool_dir = tools_dir / "bad_schema_tool"
        tool_dir.mkdir()

        manifest = {"name": "bad_schema_tool", "entry_function": "register"}
        (tool_dir / "manifest.json").write_text(json.dumps(manifest))

        # Create invalid JSON in output.json
        (tool_dir / "output.json").write_text("{invalid json}")

        # Mock the tool module with a register function
        mock_tool_module = Mock()

        def mock_register(param: str) -> dict:
            return {"result": param}

        mock_tool_module.register = mock_register

        # Setup: tool.py imports successfully, output_model.py doesn't exist
        mock_import.side_effect = [
            mock_tool_module,  # First call: tools.bad_schema_tool.tool
            ImportError("No module"),  # Second call: tools.bad_schema_tool.output_model
        ]

        mock_mcp = Mock()
        mock_mcp.tool = Mock(return_value=lambda f: f)

        result = load_tools_from_directory(mock_mcp, str(tools_dir))

        # Tool should still load successfully, but warning should be printed
        assert "bad_schema_tool" in result["loaded"]
        captured = capsys.readouterr()
        assert "Could not load output schema for bad_schema_tool" in captured.out
