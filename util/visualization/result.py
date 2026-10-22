"""Package a card as an MCP Apps tool result.

The host renders `structured_content` (the Prefab app) for the user; the model
only sees `content`, so the text summary has to carry what the model needs to
talk about the result (layers, ranges, caveats).
"""

from __future__ import annotations

from fastmcp.tools.base import ToolResult
from mcp.types import TextContent
from prefab_ui import PrefabApp


def ui_result(view, summary: str, title: str = "Earthdata") -> ToolResult:
    """Card for the user (structured_content) plus a text summary for the model."""
    return ToolResult(
        content=[TextContent(type="text", text=summary)],
        structured_content=PrefabApp(title=title, view=view),
    )


def error_result(message: str) -> ToolResult:
    """Validation/lookup failures go back to the model as text so it can retry."""
    return ToolResult(content=[TextContent(type="text", text=message)], is_error=True)
