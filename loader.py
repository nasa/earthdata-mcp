"""Simplified tool loader."""

import importlib
import inspect
import json
import logging
from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import Any

from langfuse import observe
from pydantic import BaseModel

from util.langfuse import flush_langfuse

logger = logging.getLogger(__name__)


class ToolManifest:
    """Handles manifest loading with sensible defaults."""

    DEFAULT_MANIFEST = {
        "description": "No description provided.",
        "tags": [],
    }

    def __init__(self, tool_dir: Path):
        self.manifest = self.DEFAULT_MANIFEST.copy()
        manifest_path = tool_dir / "manifest.json"

        if manifest_path.exists():
            try:
                with open(manifest_path, encoding="utf-8") as f:
                    file_manifest = json.load(f)
                self.manifest.update(file_manifest)
            except (FileNotFoundError, PermissionError, json.JSONDecodeError) as e:
                raise ValueError(f"Could not read manifest.json: {e}") from e
        else:
            raise FileNotFoundError(f"No manifest.json found at {manifest_path}")

    def get(self, key: str, default=None):
        """Get a manifest value."""
        return self.manifest.get(key, default)

    @property
    def name(self) -> str:
        """Get the tool name from the manifest (required)."""
        if "name" not in self.manifest:
            raise ValueError("manifest.json missing required 'name' field")
        return self.manifest["name"]

    @property
    def description(self) -> str:
        """Get the tool description from the manifest."""
        return self.manifest["description"]

    @property
    def version(self) -> str:
        """Get the tool version from the manifest (required)."""
        if "version" not in self.manifest:
            raise ValueError("manifest.json missing required 'version' field")
        return self.manifest["version"]

    @property
    def tags(self) -> list:
        """Get the tool tags from the manifest, returning empty list if not specified."""
        return self.manifest.get("tags", [])

    @property
    def annotations(self) -> dict[str, Any]:
        """Get the tool annotations from the manifest, returning empty dict if not specified."""
        return self.manifest.get("annotations", {})


def create_simple_tool(
    manifest_path: Path,
    func: Callable[..., Any],
    output_schema: dict | type[BaseModel] | None = None,
) -> Callable:
    """
    Factory function for creating simple tools without a class.

    Args:
        manifest_path: Path to the tool's directory (containing manifest.json)
        func: The function implementing the tool logic
        output_schema: Optional output schema (dict or Pydantic model class) for the tool

    Returns:
        A register function compatible with the MCP loader

    Example:
        def my_tool_logic(keyword: str) -> dict:
            return {"result": f"Searched for {keyword}"}

        register = create_simple_tool(Path(__file__).parent, my_tool_logic)
    """
    manifest = ToolManifest(manifest_path)

    def register(mcp):
        tool_kwargs = {
            "name": manifest.name,
            "description": manifest.description,
            "version": manifest.version,
            "output_schema": output_schema,
        }
        if manifest.annotations:
            tool_kwargs["annotations"] = manifest.annotations

        @mcp.tool(**tool_kwargs)
        @wraps(func)
        @observe(name=manifest.name)
        async def wrapper(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                flush_langfuse()

        return wrapper

    return register


def load_tools_from_directory(mcp, tools_dir="tools"):
    """Load all tools from the tools directory."""
    tools_dir = Path(tools_dir)
    loaded = []

    for tool_folder in sorted(tools_dir.iterdir()):
        if not tool_folder.is_dir() or tool_folder.name.startswith((".", "__")):
            continue

        manifest_path = tool_folder / "manifest.json"
        if not manifest_path.exists():
            logger.info("[SKIP] %s: No manifest.json", tool_folder.name)
            continue

        try:
            # Load manifest using ToolManifest
            manifest = ToolManifest(tool_folder)

            tool_name = manifest.get("name")
            tool_entry = manifest.get("entry_function")
            if not tool_name:
                raise ValueError("manifest.json missing 'name' field")
            enabled = manifest.get("enabled", True)
            if not isinstance(enabled, bool):
                raise ValueError(
                    "manifest.json 'enabled' field must be a boolean for "
                    f"tool '{tool_folder.name}'"
                )
            if enabled is False:
                logger.info("[SKIP] %s: Disabled in manifest", tool_folder.name)
                continue

            # Import the tool module
            module_path = f"{tools_dir.name}.{tool_folder.name}.tool"
            module = importlib.import_module(module_path)

            # Get the tool function
            if not hasattr(module, tool_entry):
                raise AttributeError(f"tool.py missing function '{tool_entry}'")

            tool_func = getattr(module, tool_entry)

            # Load output schema - prefer Pydantic model over JSON schema
            output_schema = None

            # Try to import output_model.py first
            try:
                output_model_path = f"{tools_dir.name}.{tool_folder.name}.output_model"
                output_module = importlib.import_module(output_model_path)

                # Look for a Pydantic model class (typically ending with 'Output')
                for attr_name in dir(output_module):
                    attr = getattr(output_module, attr_name)
                    if (
                        inspect.isclass(attr)
                        and issubclass(attr, BaseModel)
                        and attr is not BaseModel
                    ):
                        output_schema = attr.model_json_schema()
                        logger.debug("Using Pydantic model %s for %s", attr_name, tool_name)
                        break
            except (ImportError, AttributeError):
                # Fall back to JSON schema if output_model.py doesn't exist
                schema_path = tool_folder / "output.json"
                if schema_path.exists():
                    try:
                        with open(schema_path, encoding="utf-8") as f:
                            output_schema = json.load(f)
                            logger.debug("Using JSON schema for %s", tool_name)
                    except Exception as e:
                        logger.warning("Could not load output schema for %s: %s", tool_name, e)

            # Register the tool using create_simple_tool
            register_func = create_simple_tool(tool_folder, tool_func, output_schema)
            register_func(mcp)

            loaded.append(tool_name)
            logger.info("[LOAD] ✓ %s", tool_name)

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("[FAIL] ✗ %s: %s", tool_folder.name, e)
            raise RuntimeError(
                f"Failed to load tool '{tool_folder.name}' from {manifest_path}"
            ) from e

    # Summary
    logger.info("\n%s", "=" * 50)
    logger.info("Loaded: %d tools", len(loaded))
    logger.info("%s\n", "=" * 50)

    return {"loaded": loaded, "failed": []}
