"""Demo tool: terra-map with hardcoded vector point locations."""

from fastmcp.tools.base import ToolResult
from mcp.types import TextContent
from prefab_ui import PrefabApp

from util.visualization import MapSpec, map_card, vector_layer

_COLLECTION_ID = "C1374742240-LAADS"

# Sample [lon, lat] points across the globe
_SAMPLE_COORDS = [
    [-119.5,  37.8],  # California
    [ -87.6,  41.8],  # Chicago
    [  -0.1,  51.5],  # London
    [  13.4,  52.5],  # Berlin
    [ 139.7,  35.7],  # Tokyo
    [ -43.2, -22.9],  # Rio de Janeiro
    [  18.4, -33.9],  # Cape Town
    [ -73.9,  40.7],  # New York
    [ 103.8,   1.4],  # Singapore
    [  37.6,  55.8],  # Moscow
]


def show_vector_map() -> ToolResult:
    """Show a terra-map with sample vector point locations.

    Demonstrates the vector_layer pipeline: a hardcoded list of [lon, lat]
    coordinates is rendered as orange circles on top of MODIS Terra GIBS imagery.
    """
    layer = vector_layer(_SAMPLE_COORDS, name="sample-points")
    spec = MapSpec(
        title=f"Vector Layer Demo — {len(_SAMPLE_COORDS)} points",
        collection_id=_COLLECTION_ID,
        layers=[layer],
    )
    return ToolResult(
        content=[TextContent(type="text", text=f"Rendered map with {len(_SAMPLE_COORDS)} vector points.")],
        structured_content=PrefabApp(title=spec.title, view=map_card(spec)),
    )
