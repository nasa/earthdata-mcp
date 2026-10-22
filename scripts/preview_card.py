"""Preview what render_map sends, without an MCP host.

Run from the repo root:
    uv run python scripts/preview_card.py            # writes preview/ and opens it
    uv run python scripts/preview_card.py --no-open

Writes three files to preview/:
    map.html          the map page alone (the iframe inside the card); quickest to iterate on
    card.html         the full Prefab card, rendered the way an MCP Apps host renders it
    tool_result.json  exactly what FastMCP returns for the tool call (text for the model +
                      structured_content for the host)

Harmony links need Earthdata Login: the script reads EARTHDATA_BEARER_TOKEN (or EDL_TOKEN)
from the environment or a .env file in the repo root or its parent, fetches the file the
same way render_map does on the server, and embeds it in the pages.

Edit SPEC / TOOL_ARGS below to try other layers.
"""

import asyncio
import json
import os
import sys
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastmcp import Client, FastMCP  # noqa: E402
from prefab_ui import PrefabApp  # noqa: E402

import tools.render_map.tool as render_map_module  # noqa: E402
from util.visualization import GeoTiffLayer, GibsLayer, MapSpec, map_card, map_html  # noqa: E402
from util.visualization.delivery import prepare_geotiff_layers  # noqa: E402

REPO = Path(__file__).resolve().parents[1]

OUT = Path("preview")

TIF = (
    "https://harmony.earthdata.nasa.gov/service-results/harmony-prod-staging/public/"
    "2ec8de62-cdbc-4e1a-aa7f-235e46fa5afd/422346436/"
    "20240615090000-JPL-L4_GHRSST-SSTfnd-MUR25-GLOB-v02.0-fv04.2_analysed_sst_reformatted.tif"
)

SPEC = MapSpec(
    title="MUR25 SST 2024-06-15",
    layers=[
        GeoTiffLayer(name="sst", title="Analysed SST", url=TIF, units="K", vmin=271, vmax=305),
        GibsLayer(name="gibs", title="GIBS MUR SST", layer="GHRSST_L4_MUR_Sea_Surface_Temperature",
                  tile_matrix_set="GoogleMapsCompatible_Level7", format="png", date="2024-06-15",
                  visible=False),
    ],
)

# The same map, as the agent would request it through the tool.
TOOL_ARGS = {"title": "MUR25 SST 2024-06-15", "geotiff_urls": [TIF], "units": "K", "vmin": 271, "vmax": 305}


def load_token() -> str | None:
    """EARTHDATA_BEARER_TOKEN / EDL_TOKEN from the environment or a .env file."""
    for env_file in (REPO / ".env", REPO.parent / ".env"):
        if not env_file.exists():
            continue
        for line in env_file.read_text().splitlines():
            key, sep, value = line.strip().partition("=")
            key = key.strip().removeprefix("export ").strip()
            if sep and key in ("EARTHDATA_BEARER_TOKEN", "EDL_TOKEN"):
                os.environ.setdefault(key, value.strip().strip("'\""))
    return os.environ.get("EARTHDATA_BEARER_TOKEN") or os.environ.get("EDL_TOKEN")


async def tool_result() -> dict:
    """Call render_map through a real FastMCP server/client, in memory."""
    mcp = FastMCP("preview")
    mcp.tool(render_map_module.render_map)  # no app=... needed just to see the payload
    async with Client(mcp) as client:
        result = await client.call_tool("render_map", TOOL_ARGS, raise_on_error=False)
    return {
        "is_error": result.is_error,
        "content (what the model sees)": [c.text for c in result.content],
        "structured_content (what the host renders)": result.structured_content,
    }


def main() -> None:
    token = load_token()
    if not token:
        print("No EARTHDATA_BEARER_TOKEN found; Harmony layers will be dropped.")
    # On the server, render_map gets the token from the MCP request; here it comes from .env.
    render_map_module._user_token = lambda: token  # pylint: disable=protected-access

    spec, notes = prepare_geotiff_layers(SPEC, token)
    for n in notes:
        print("note:", n)
    OUT.mkdir(exist_ok=True)
    (OUT / "map.html").write_text(map_html(spec), encoding="utf-8")
    (OUT / "card.html").write_text(
        PrefabApp(title=spec.title, view=map_card(spec, extra_notes=notes)).html(), encoding="utf-8"
    )
    (OUT / "tool_result.json").write_text(json.dumps(asyncio.run(tool_result()), indent=2), encoding="utf-8")
    for name in ("map.html", "card.html", "tool_result.json"):
        print(OUT / name)
    if "--no-open" not in sys.argv:
        webbrowser.open((OUT / "card.html").resolve().as_uri())


if __name__ == "__main__":
    main()
