"""Helpers for MCP Apps (Prefab UI) output."""

from __future__ import annotations

import json


def build_map_result(
    data: dict,
    collection_id: str,
    title: str,
) -> dict:
    """Return a ToolResult with a Prefab map card."""
    from fastmcp.tools.base import ToolResult
    from mcp.types import TextContent
    from prefab_ui import PrefabApp

    from util.visualization import MapSpec, map_card

    spec = MapSpec(title=title, collection_id=collection_id)
    return ToolResult(
        content=[TextContent(type="text", text=json.dumps(data))],
        structured_content=PrefabApp(title=title, view=map_card(spec)),
    )
