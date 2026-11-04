"""Demo tool: terra-map with a georeferenced image layer."""

import base64
import struct
import zlib

from fastmcp.tools.base import ToolResult
from mcp.types import TextContent
from prefab_ui import PrefabApp

from util.visualization import MapSpec, image_layer, map_card

_COLLECTION_ID = "C1374742240-LAADS"
_EUROPE_EXTENT = [-10.0, 35.0, 40.0, 70.0]


def _solid_png(r: int, g: int, b: int, a: int = 180, w: int = 64, h: int = 64) -> str:
    """Return a data URI for a small solid-colour RGBA PNG (no Pillow needed)."""

    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)
    row = b"\x00" + bytes([r, g, b, a]) * w
    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(row * h))
        + chunk(b"IEND", b"")
    )
    return "data:image/png;base64," + base64.b64encode(png).decode()


def show_layer_map() -> ToolResult:
    """Show a terra-map with a semi-transparent black image layer over Europe.

    Demonstrates the image-layer pipeline: a georeferenced PNG is composited
    on top of MODIS Terra GIBS imagery using ol.source.ImageStatic.
    """
    layer = image_layer(
        _solid_png(0, 0, 0, 180), _EUROPE_EXTENT, opacity=0.8, name="europe-overlay"
    )
    spec = MapSpec(
        title="MODIS Terra + Image Layer (Europe)",
        collection_id=_COLLECTION_ID,
        layers=[layer],
    )
    return ToolResult(
        content=[
            TextContent(
                type="text",
                text="Rendered map with georeferenced image layer over Europe.",
            )
        ],
        structured_content=PrefabApp(title=spec.title, view=map_card(spec)),
    )
