"""Map cards for MCP Apps hosts.

Build a renderer-neutral MapSpec, then turn it into a Prefab Card
(map_card) or raw HTML (map_html) embedding a <terra-map>.
    specs.py     Renderer-neutral contract (MapSpec)
    config.py    Pinned CDN assets
    map_card.py  MapSpec -> Prefab Card with an embedded <terra-map>
    result.py    Card + text summary -> ToolResult
"""

from util.visualization.layers import image_layer, vector_layer, wms_layer
from util.visualization.map_card import map_card, map_html
from util.visualization.specs import MapSpec

__all__ = [
    "MapSpec",
    "image_layer",
    "map_card",
    "map_html",
    "vector_layer",
    "wms_layer",
]
