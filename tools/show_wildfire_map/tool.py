"""Show active wildfire locations from EONET as a vector layer on a terra-map."""

import json
import urllib.request

from fastmcp.exceptions import ToolError
from fastmcp.tools.base import ToolResult
from mcp.types import TextContent
from prefab_ui import PrefabApp

from util.visualization import MapSpec, map_card, vector_layer

_EONET_URL = "https://eonet.gsfc.nasa.gov/api/v3/events?category=wildfires&status=open&limit=200"
_COLLECTION_ID = "C1374742240-LAADS"


def _fetch_fire_coords() -> list[list[float]]:
    """Return [[lon, lat], ...] for all open wildfire events from EONET."""
    try:
        with urllib.request.urlopen(_EONET_URL, timeout=10) as resp:
            data = json.loads(resp.read())
    except Exception as exc:
        raise ToolError(f"Could not fetch EONET events: {exc}") from exc

    coords = []
    for event in data.get("events", []):
        for geom in event.get("geometry", []):
            if geom.get("type") == "Point":
                coords.append(geom["coordinates"])
    return coords


def show_wildfire_map() -> ToolResult:
    """Show active wildfire locations on a terra-map.

    Fetches open wildfire events from the NASA EONET API and renders them
    as orange vector points on top of MODIS Terra GIBS satellite imagery.
    """
    coords = _fetch_fire_coords()
    if not coords:
        raise ToolError("No active wildfire events returned from EONET.")

    layer = vector_layer(coords, name="wildfire-events")
    spec = MapSpec(
        title=f"Active Wildfires — {len(coords)} events (EONET)",
        collection_id=_COLLECTION_ID,
        layers=[layer],
    )
    return ToolResult(
        content=[TextContent(type="text", text=f"Rendered wildfire map with {len(coords)} active fire locations from EONET.")],
        structured_content=PrefabApp(title=spec.title, view=map_card(spec)),
    )
