"""Tests for the loader.py module."""

import json
import logging
from unittest.mock import Mock, patch

import pytest

from loader import ToolManifest, create_simple_tool, load_tools_from_directory


class TestToolManifest:
    """Test cases for ToolManifest class."""

    def test_manifest_with_valid_file(self, tmp_path):
        """Test loading a valid manifest.json file."""
        manifest_data = {
            "name": "test_tool",
            "version": "1.0.0",
            "description": "A test tool",
            "tags": ["test", "example"],
        }
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest_data))

        manifest = ToolManifest(tmp_path)

        assert manifest.name == "test_tool"
        assert manifest.version == "1.0.0"
        assert manifest.description == "A test tool"
        assert manifest.tags == ["test", "example"]

    def test_manifest_without_file(self, tmp_path):
        """Test behavior when manifest.json doesn't exist."""
        with pytest.raises(FileNotFoundError, match="No manifest.json found"):
            ToolManifest(tmp_path)

    def test_manifest_with_invalid_json(self, tmp_path):
        """Test behavior when manifest.json contains invalid JSON."""
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text("{invalid json}")

        with pytest.raises(ValueError, match="Could not read manifest.json"):
            ToolManifest(tmp_path)

    def test_manifest_get_method(self, tmp_path):
        """Test the get method of ToolManifest."""
        manifest_data = {"name": "test_tool", "version": "1.0.0", "custom_field": "custom_value"}
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest_data))

        manifest = ToolManifest(tmp_path)

        assert manifest.get("name") == "test_tool"
        assert manifest.get("custom_field") == "custom_value"
        assert manifest.get("nonexistent", "default") == "default"

    def test_manifest_missing_required_keys(self, tmp_path):
        """Test behavior when a valid manifest.json is missing required keys."""
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps({"description": "No name or version!"}))

        manifest = ToolManifest(tmp_path)

        with pytest.raises(ValueError, match="missing required 'name' field"):
            _ = manifest.name
        with pytest.raises(ValueError, match="missing required 'version' field"):
            _ = manifest.version

    def test_manifest_annotations_from_nested_object(self, tmp_path):
        """Test loading annotations from the nested annotations object."""
        manifest_data = {
            "name": "test_tool",
            "version": "1.0.0",
            "annotations": {
                "readOnlyHint": True,
                "destructiveHint": False,
            },
        }
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest_data))

        manifest = ToolManifest(tmp_path)

        assert manifest.annotations == {
            "readOnlyHint": True,
            "destructiveHint": False,
        }

    def test_manifest_annotations_ignores_legacy_root_keys(self, tmp_path):
        """Test root-level annotation hint keys are ignored."""
        manifest_data = {
            "name": "test_tool",
            "version": "1.0.0",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        }
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest_data))

        manifest = ToolManifest(tmp_path)

        assert manifest.annotations == {}


class TestCreateSimpleTool:
    """Test cases for create_simple_tool function."""

    def test_create_simple_tool_basic(self, tmp_path):
        """Test creating a simple tool with basic configuration."""
        manifest_data = {"name": "test_tool", "version": "1.0.0", "description": "A test tool"}
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
        assert call_kwargs["version"] == manifest_data["version"]
        assert call_kwargs["output_schema"] is None

    def test_create_simple_tool_with_output_schema(self, tmp_path):
        """Test creating a tool with output schema."""
        manifest_data = {"name": "test_tool", "version": "1.0.0", "description": "Test"}
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
        assert call_kwargs["version"] == manifest_data["version"]

    def test_create_simple_tool_passes_annotations(self, tmp_path):
        """Test creating a tool forwards manifest annotations into mcp.tool."""
        manifest_data = {
            "name": "test_tool",
            "version": "1.0.0",
            "description": "Test",
            "annotations": {
                "readOnlyHint": True,
                "destructiveHint": False,
            },
        }
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest_data))

        def tool_func(keyword: str) -> dict:
            return {"result": keyword}

        register_func = create_simple_tool(tmp_path, tool_func)

        mock_mcp = Mock()
        mock_tool_decorator = Mock(return_value=lambda f: f)
        mock_mcp.tool = mock_tool_decorator

        register_func(mock_mcp)

        call_kwargs = mock_mcp.tool.call_args[1]
        assert call_kwargs["annotations"] == {
            "readOnlyHint": True,
            "destructiveHint": False,
        }

    @pytest.mark.asyncio
    @patch("loader.flush_langfuse")
    async def test_create_simple_tool_wrapper_execution(self, mock_flush, tmp_path):
        """Test that the wrapper function executes and returns results correctly."""
        manifest_data = {"name": "test_tool", "version": "1.0.0", "description": "Test"}
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
                # Mock the @observe decorator to return the function unchanged
                return func

            return decorator

        mock_mcp = Mock()
        mock_mcp.tool = mock_tool_decorator

        register_func(mock_mcp)

        # In fastmcp v3, the tool decorator doesn't return the wrapper,
        # but our loader specifically wraps the tool_func inside wrapper()
        # pylint: disable=not-callable
        result = await wrapper_func(keyword="test")
        assert result == {"result": "Processed test"}
        mock_flush.assert_called_once()


class TestLoadToolsFromDirectory:
    """Test cases for load_tools_from_directory function."""

    @patch("loader.importlib.import_module")
    def test_load_tools_success(self, mock_import, tmp_path, caplog):
        """Test successfully loading tools from directory."""
        caplog.set_level(logging.DEBUG)
        tools_dir = tmp_path / "tools"
        tools_dir.mkdir()

        # Create a valid tool
        tool_dir = tools_dir / "test_tool"
        tool_dir.mkdir()

        manifest = {
            "name": "test_tool",
            "version": "1.0.0",
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

        assert "✓ test_tool" in caplog.text

    def test_load_tools_skip_hidden_dirs(self, tmp_path):
        """Test that hidden directories are skipped."""
        tools_dir = tmp_path / "tools"
        tools_dir.mkdir()

        # Create hidden directory
        hidden_dir = tools_dir / ".hidden"
        hidden_dir.mkdir()
        (hidden_dir / "manifest.json").write_text(
            json.dumps({"name": "hidden", "version": "1.0.0"})
        )

        mock_mcp = Mock()
        result = load_tools_from_directory(mock_mcp, str(tools_dir))

        assert len(result["loaded"]) == 0
        assert len(result["failed"]) == 0

    def test_load_tools_missing_manifest(self, tmp_path, caplog):
        """Test behavior when tool directory has no manifest.json."""
        caplog.set_level(logging.DEBUG)
        tools_dir = tmp_path / "tools"
        tools_dir.mkdir()

        tool_dir = tools_dir / "no_manifest_tool"
        tool_dir.mkdir()

        mock_mcp = Mock()
        result = load_tools_from_directory(mock_mcp, str(tools_dir))

        assert "[SKIP] no_manifest_tool: No manifest.json" in caplog.text
        assert len(result["loaded"]) == 0

    @patch("loader.importlib.import_module")
    def test_load_tools_skips_disabled_manifest(self, mock_import, tmp_path, caplog):
        """Tools with enabled=false in manifest should be skipped."""
        caplog.set_level(logging.DEBUG)
        tools_dir = tmp_path / "tools"
        tools_dir.mkdir()

        tool_dir = tools_dir / "disabled_tool"
        tool_dir.mkdir()
        (tool_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "name": "disabled_tool",
                    "version": "1.0.0",
                    "entry_function": "register",
                    "enabled": False,
                }
            )
        )

        mock_mcp = Mock()
        result = load_tools_from_directory(mock_mcp, str(tools_dir))

        assert not result["loaded"]
        assert not result["failed"]
        mock_import.assert_not_called()

        assert "[SKIP] disabled_tool: Disabled in manifest" in caplog.text

    @patch("loader.importlib.import_module")
    def test_load_tools_fails_on_non_boolean_enabled(self, mock_import, tmp_path, caplog):
        """Tools with non-boolean enabled should fail fast with a clear error."""
        tools_dir = tmp_path / "tools"
        tools_dir.mkdir()

        tool_dir = tools_dir / "bad_enabled_tool"
        tool_dir.mkdir()
        (tool_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "name": "bad_enabled_tool",
                    "version": "1.0.0",
                    "entry_function": "register",
                    "enabled": "false",
                }
            )
        )

        mock_mcp = Mock()
        with pytest.raises(RuntimeError, match="Failed to load tool 'bad_enabled_tool'"):
            load_tools_from_directory(mock_mcp, str(tools_dir))

        mock_import.assert_not_called()
        assert "'enabled' field must be a boolean" in caplog.text

    @patch("loader.importlib.import_module")
    def test_load_tools_missing_entry_function(self, mock_import, tmp_path, caplog):
        """Test behavior when tool module is missing entry function."""
        tools_dir = tmp_path / "tools"
        tools_dir.mkdir()

        tool_dir = tools_dir / "broken_tool"
        tool_dir.mkdir()

        manifest = {"name": "broken_tool", "version": "1.0.0", "entry_function": "register"}
        (tool_dir / "manifest.json").write_text(json.dumps(manifest))

        # Mock module without the register function
        mock_module = Mock(spec=[])
        mock_import.return_value = mock_module

        mock_mcp = Mock()
        with pytest.raises(RuntimeError, match="Failed to load tool 'broken_tool'"):
            load_tools_from_directory(mock_mcp, str(tools_dir))

        assert "✗ broken_tool" in caplog.text

    @patch("loader.importlib.import_module")
    def test_load_tools_with_pydantic_output_schema(self, mock_import, tmp_path, caplog):
        """Test loading tool with Pydantic output schema."""
        caplog.set_level(logging.DEBUG)
        tools_dir = tmp_path / "tools"
        tools_dir.mkdir()

        tool_dir = tools_dir / "pydantic_tool"
        tool_dir.mkdir()

        manifest = {"name": "pydantic_tool", "version": "1.0.0", "entry_function": "register"}
        (tool_dir / "manifest.json").write_text(json.dumps(manifest))

        mock_tool_module = Mock()

        def mock_register(param: str) -> dict:
            return {"result": param}

        mock_tool_module.register = mock_register

        # Create a real module-like object to bypass mock's weird dir() behavior
        class DummyModule:
            """Dummy module for mocking imports."""

        from pydantic import BaseModel

        class DummyOutput(BaseModel):
            """Dummy Pydantic output model."""

            result: str

        mock_output_module = DummyModule()
        mock_output_module.DummyOutput = DummyOutput  # pylint: disable=attribute-defined-outside-init

        mock_import.side_effect = [
            mock_tool_module,  # First call: tool.py
            mock_output_module,  # Second call: output_model.py
        ]

        mock_mcp = Mock()
        mock_mcp.tool = Mock(return_value=lambda f: f)

        result = load_tools_from_directory(mock_mcp, str(tools_dir))

        assert "pydantic_tool" in result["loaded"]
        assert "Using Pydantic model DummyOutput for pydantic_tool" in caplog.text

    @patch("loader.importlib.import_module")
    def test_load_tools_with_output_schema(self, mock_import, tmp_path, caplog):
        """Test loading tool with JSON output schema."""
        caplog.set_level(logging.DEBUG)
        tools_dir = tmp_path / "tools"
        tools_dir.mkdir()

        tool_dir = tools_dir / "schema_tool"
        tool_dir.mkdir()

        manifest = {"name": "schema_tool", "version": "1.0.0", "entry_function": "register"}
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

        # This should hit line 159 - the JSON schema loading print statement
        assert "Using JSON schema for schema_tool" in caplog.text

    @patch("loader.importlib.import_module")
    def test_load_tools_missing_name_field(self, mock_import, tmp_path, caplog):
        """Test behavior when manifest.json is missing the 'name' field."""
        caplog.set_level(logging.DEBUG)
        tools_dir = tmp_path / "tools"
        tools_dir.mkdir()

        tool_dir = tools_dir / "no_name_tool"
        tool_dir.mkdir()

        # Manifest without 'name' field
        manifest = {
            "description": "Tool without name",
            "entry_function": "register",
            "version": "1.0.0",
        }
        (tool_dir / "manifest.json").write_text(json.dumps(manifest))

        mock_mcp = Mock()
        with pytest.raises(RuntimeError, match="Failed to load tool 'no_name_tool'"):
            load_tools_from_directory(mock_mcp, str(tools_dir))

        assert "✗ no_name_tool" in caplog.text
        assert "missing 'name' field" in caplog.text
        mock_import.assert_not_called()

    @patch("loader.importlib.import_module")
    def test_load_tools_invalid_output_schema(self, mock_import, tmp_path, caplog):
        """Test behavior when output.json contains invalid JSON."""
        tools_dir = tmp_path / "tools"
        tools_dir.mkdir()

        tool_dir = tools_dir / "bad_schema_tool"
        tool_dir.mkdir()

        manifest = {"name": "bad_schema_tool", "version": "1.0.0", "entry_function": "register"}
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

        assert "Could not load output schema for bad_schema_tool" in caplog.text
