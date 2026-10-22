"""Map and chart cards for MCP Apps hosts.

Layout:
    specs.py     Renderer-neutral contract (MapSpec + layers, VizSpec)
    builders.py  Tool outputs (Harmony links, CMR boxes) -> specs
    gibs.py      CMR collection -> GIBS layers (edsc.extra.serverless.gibs tag)
    colormaps.py Shared colormap stops
    config.py    Pinned CDN assets, CSP domain lists
    map_card.py  MapSpec -> Prefab Card with an embedded <terra-map>
    viz_card.py  VizSpec -> Prefab Card (charts / images)
    result.py    Card + text summary -> ToolResult
"""

from util.visualization.builders import (
    footprints_layer,
    geotiff_layers_from_links,
    images_from_links,
    parse_cmr_box,
    split_result_links,
)
from util.visualization.map_card import map_card, map_html
from util.visualization.result import error_result, ui_result
from util.visualization.specs import (
    FootprintLayer,
    GeoTiffLayer,
    GibsLayer,
    ImageItem,
    MapSpec,
    Series,
    ValueScale,
    VizSpec,
)
from util.visualization.viz_card import viz_card

__all__ = [
    "FootprintLayer",
    "GeoTiffLayer",
    "GibsLayer",
    "ImageItem",
    "MapSpec",
    "Series",
    "ValueScale",
    "VizSpec",
    "error_result",
    "footprints_layer",
    "geotiff_layers_from_links",
    "images_from_links",
    "map_card",
    "map_html",
    "parse_cmr_box",
    "split_result_links",
    "ui_result",
    "viz_card",
]
