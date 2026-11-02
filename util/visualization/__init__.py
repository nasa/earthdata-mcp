"""Map cards for MCP Apps hosts.

Layout:
    specs.py     Renderer-neutral contract (MapSpec)
    config.py    Pinned CDN assets
    map_card.py  MapSpec -> Prefab Card with an embedded <terra-map>
    result.py    Card + text summary -> ToolResult
"""

from util.visualization.map_card import map_card, map_html
from util.visualization.specs import MapSpec

__all__ = [
    "MapSpec",
    "map_card",
    "map_html",
]
