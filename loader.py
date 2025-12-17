"""Simplified tool loader."""

import json
import importlib
import inspect
from pathlib import Path
from typing import Any, Callable
from functools import wraps


class ToolManifest:
    """Handles manifest loading with sensible defaults."""

    DEFAULT_MANIFEST = {
        "name": "unnamed_tool",
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
            except Exception as e:
                print(f"[WARNING] Could not read manifest.json: {e}")
        else:
            print(f"[WARNING] No manifest.json found at {manifest_path}")

    def get(self, key: str, default=None):
        """Get a manifest value."""
        return self.manifest.get(key, default)

    @property
    def name(self) -> str:
        return self.manifest["name"]

    @property
    def description(self) -> str:
        return self.manifest["description"]

    @property
    def tags(self) -> list:
        return self.manifest.get("tags", [])


def create_simple_tool(
    manifest_path: Path,
    func: Callable[..., Any],
    output_schema: dict | None = None,
) -> Callable:
    """
    Factory function for creating simple tools without a class.

    Args:
        manifest_path: Path to the tool's directory (containing manifest.json)
        func: The function implementing the tool logic
        output_schema: Optional output schema dictionary for the tool

    Returns:
        A register function compatible with the MCP loader

    Example:
        def my_tool_logic(keyword: str) -> dict:
            return {"result": f"Searched for {keyword}"}

        register = create_simple_tool(Path(__file__).parent, my_tool_logic)
    """
    manifest = ToolManifest(manifest_path)

    def register(mcp):
        @mcp.tool(
            name=manifest.name,
            description=manifest.description,
            output_schema=output_schema,
            # tags=set(manifest.tags) if manifest.tags else None,
        )
        @wraps(func)
        async def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            return result

        # copy signature explicitly
        wrapper.__signature__ = inspect.signature(func)

        return wrapper

    return register


def load_tools_from_directory(mcp, tools_dir="tools"):
    """Load all tools from the tools directory."""
    tools_dir = Path(tools_dir)
    loaded = []
    failed = []

    for tool_folder in sorted(tools_dir.iterdir()):
        if not tool_folder.is_dir() or tool_folder.name.startswith((".", "__")):
            continue

        manifest_path = tool_folder / "manifest.json"
        if not manifest_path.exists():
            print(f"[SKIP] {tool_folder.name}: No manifest.json")
            continue

        try:
            # Load manifest
            with open(manifest_path, encoding="utf-8") as f:
                manifest = json.load(f)

            tool_name = manifest.get("name")
            tool_entry = manifest.get("entry_function")
            if not tool_name:
                raise ValueError("manifest.json missing 'name' field")

            # Import the tool module
            module_path = f"{tools_dir.name}.{tool_folder.name}.tool"
            module = importlib.import_module(module_path)

            # Get the tool function
            if not hasattr(module, tool_entry):
                raise AttributeError(f"tool.py missing function '{tool_entry}'")

            tool_func = getattr(module, tool_entry)

            # Load output schema if available
            output_schema = None
            schema_path = tool_folder / "output.json"
            if schema_path.exists():
                try:
                    with open(schema_path, encoding="utf-8") as f:
                        output_schema = json.load(f)
                except Exception as e:
                    print(
                        f"[WARNING] Could not load output schema for {tool_name}: {e}"
                    )

            # Register the tool using create_simple_tool
            register_func = create_simple_tool(tool_folder, tool_func, output_schema)
            register_func(mcp)

            loaded.append(tool_name)
            print(f"[LOAD] ✓ {tool_name}")

        except Exception as e:
            failed.append(tool_folder.name)
            print(f"[FAIL] ✗ {tool_folder.name}: {e}")

    # Summary
    print(f"\n{'='*50}")
    print(f"Loaded: {len(loaded)} tools")
    if failed:
        print(f"Failed: {len(failed)} tools: {', '.join(failed)}")
    print(f"{'='*50}\n")

    return {"loaded": loaded, "failed": failed}
