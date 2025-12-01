"""Base classes and utilities for creating MCP tools."""

import json
import inspect
from pathlib import Path
from typing import Any, Callable
from toon import encode
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
                with open(manifest_path) as f:
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
) -> Callable:
    """
    Factory function for creating simple tools without a class.

    Args:
        manifest_path: Path to the tool's directory (containing manifest.json)
        func: The function implementing the tool logic

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
            # tags=set(manifest.tags) if manifest.tags else None,
        )
        @wraps(func)
        async def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            return [encode(result)]

        # copy signature explicitly
        wrapper.__signature__ = inspect.signature(func)

        return wrapper

    return register
