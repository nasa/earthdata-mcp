"""Client capability detection and helpers for MCP Apps (Prefab UI) output."""

from __future__ import annotations

import json

import mcp.types as mt
from fastmcp import Context
from fastmcp.server.middleware import Middleware, MiddlewareContext

# Clients known to render MCP Apps structured_content (Prefab UI).
_CAPABLE_CLIENTS = frozenset(
    {
        "claude desktop",
        "claude code",
        "cursor",
        "mcp inspector",
    }
)


class MCPAppsMiddleware(Middleware):
    """Stores whether the connected client supports MCP Apps in session state.

    Tools check ``await ctx.get_state("mcp_apps_enabled")`` to decide whether
    to attach a Prefab UI card. Unknown clients default to False.
    """

    async def on_initialize(
        self,
        context: MiddlewareContext[mt.InitializeRequest],
        call_next,
    ):
        result = await call_next(context)
        try:
            name = (context.message.params.clientInfo.name or "").lower()
            capable = any(c in name for c in _CAPABLE_CLIENTS)
        except AttributeError:
            capable = False
        if context.fastmcp_context is not None:
            await context.fastmcp_context.set_state("mcp_apps_enabled", capable)
        return result


def build_map_result(
    data: dict,
    collection_id: str,
    title: str,
) -> dict:
    """Return a ToolResult with a map card for capable clients, or data unchanged.

    Checks ``mcp_apps_enabled`` session state set by MCPAppsMiddleware.
    """
    # enabled = ctx is not None and (await ctx.get_state("mcp_apps_enabled") or False)
    # if not enabled:
    #     return data
    from fastmcp.tools.base import ToolResult
    from mcp.types import TextContent
    from prefab_ui import PrefabApp

    from util.visualization import MapSpec, map_card

    spec = MapSpec(title=title, collection_id=collection_id)
    return ToolResult(
        content=[TextContent(type="text", text=json.dumps(data))],
        structured_content=PrefabApp(title=title, view=map_card(spec)),
    )
