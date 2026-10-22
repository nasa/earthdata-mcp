"""Mock FastMCP server: a layered terra-map card and a chart card, for the MCP Inspector.

    pip install "fastmcp[apps]"
    python server.py                 # http://localhost:8765/mcp (streamable HTTP)
    python server.py --preview       # write map_card.html / chart_card.html and stop

Tools:
    show_map    terra-map with up to three stacked layers:
                  1. GIBS imagery (tiles straight from gibs.earthdata.nasa.gov)
                  2. the Harmony MUR SST GeoTIFF (fetched here with your EDL token, embedded)
                  3. a semi-transparent black box over Europe (a vector layer)
    show_chart  a Prefab line chart (mock numbers, labelled as such)

The GeoTIFF source is GEOTIFF_SOURCE (a URL or a local file path), defaulting to the
Harmony link below. Harmony links need EARTHDATA_BEARER_TOKEN (or EDL_TOKEN) in the
environment or a .env file here or one folder up. If the GeoTIFF can't be fetched, the
map still renders the other layers and says why.
"""

import base64
import io
import json
import os
import struct
import sys
import threading
import urllib.parse
import urllib.request
import zlib
from functools import lru_cache
from pathlib import Path
from typing import Literal

import numpy as np
import requests as _requests
import tifffile as _tifffile
from starlette.requests import Request
from starlette.responses import HTMLResponse

from fastmcp import FastMCP
from fastmcp.apps.config import PrefabAppConfig, ResourceCSP
from fastmcp.tools.base import ToolResult
from mcp.types import TextContent
from prefab_ui import PrefabApp
from prefab_ui.components.card import Card, CardContent, CardDescription, CardHeader, CardTitle
from prefab_ui.components.charts import ChartSeries, LineChart
from prefab_ui.components.embed import Embed
from prefab_ui.components.markdown import Markdown

HERE = Path(__file__).resolve().parent

HARMONY_URL = (
    "https://harmony.earthdata.nasa.gov/service-results/harmony-prod-staging/public/"
    "2ec8de62-cdbc-4e1a-aa7f-235e46fa5afd/422346436/"
    "20240615090000-JPL-L4_GHRSST-SSTfnd-MUR25-GLOB-v02.0-fv04.2_analysed_sst_reformatted.tif"
)

# GIBS layers known to work with the Web Mercator REST endpoint, with the tile matrix set
# and format each one needs (the wrong level returns 400s).
GIBS_LAYERS = {
    "MODIS_Terra_CorrectedReflectance_TrueColor": ("MODIS Terra true color", "GoogleMapsCompatible_Level9", "jpg"),
    "VIIRS_SNPP_CorrectedReflectance_TrueColor": ("VIIRS SNPP true color", "GoogleMapsCompatible_Level9", "jpg"),
    "GHRSST_L4_MUR_Sea_Surface_Temperature": ("GIBS MUR SST", "GoogleMapsCompatible_Level7", "png"),
}
EUROPE = [-10.0, 35.0, 30.0, 60.0]  # [west, south, east, north]

mcp = FastMCP("viz-mock")

# The card's iframe Content-Security-Policy is fixed when the tool is registered, so every
# host the map page touches is listed here. (The GeoTIFF is embedded, so it needs none.)
MAP_HOSTS = [
    "https://cdn.jsdelivr.net",          # terra-ui, OpenLayers, geotiff.js
    "https://server.arcgisonline.com",   # terra-map basemap imagery
    "https://basemaps.arcgis.com",       # terra-map borders and labels (vector tiles)
    "https://fonts.googleapis.com",      # terra theme fonts
    "https://fonts.gstatic.com",
    "https://unpkg.com",                 # draw-toolbar sprite terra references
    "https://gibs.earthdata.nasa.gov",   # GIBS imagery tiles
    "https://*.amazonaws.com",           # Harmony output files on S3
]
MAP_APP = PrefabAppConfig(csp=ResourceCSP(resource_domains=MAP_HOSTS, connect_domains=MAP_HOSTS))

# Cached iframe HTML served by the custom route below.
_geotiff_iframe_html: str = "<p style='color:#aaa;font-family:monospace'>Call show_geotiff_map first.</p>"


@mcp.custom_route("/geotiff-iframe", methods=["GET"])
async def serve_geotiff_iframe(request: Request) -> HTMLResponse:
    # No CSP: terra-map (ArcGIS JS API) needs many arcgis.com sub-domains for
    # basemap config/vector tiles; a restrictive CSP blocks them and shows white.
    # The file:// standalone preview also has no CSP and works fine.
    return HTMLResponse(_geotiff_iframe_html)


# ----------------------------------------------------------------------------- GeoTIFF fetch
def load_token() -> str | None:
    for env_file in (HERE / ".env", HERE.parent / ".env"):
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                key, sep, value = line.strip().partition("=")
                key = key.strip().removeprefix("export ").strip()
                if sep and key in ("EARTHDATA_BEARER_TOKEN", "EDL_TOKEN"):
                    os.environ.setdefault(key, value.strip().strip("'\""))
    return os.environ.get("EARTHDATA_BEARER_TOKEN") or os.environ.get("EDL_TOKEN")


_MAX_GEOTIFF_BYTES = 5 * 1024 * 1024   # 5 MB inline limit (matches production)
_FETCH_TIMEOUT_S = 40                   # total wall-clock budget for the download


def _download_geotiff(source: str) -> tuple[str, str]:
    """Worker: fetch GeoTIFF bytes, return (base64, info) or ('', error)."""
    if not source.startswith(("http://", "https://")):
        try:
            raw = Path(source).read_bytes()
            return base64.b64encode(raw).decode("ascii"), f"{Path(source).name} ({len(raw)//1024} KB)"
        except Exception as exc:
            return "", str(exc)

    token = load_token()
    url = source
    with _requests.Session() as session:
        for _ in range(8):
            host = urllib.parse.urlsplit(url).hostname or ""
            if host == "urs.earthdata.nasa.gov":
                return "", "Earthdata Login rejected (token missing or expired)"
            headers = {"User-Agent": "viz-mock"}
            if token and host.endswith("earthdata.nasa.gov"):
                headers["Authorization"] = f"Bearer {token}"
            try:
                resp = session.get(url, headers=headers, allow_redirects=False,
                                   stream=True, timeout=(10, 30))
            except _requests.RequestException as exc:
                return "", str(exc)
            if resp.status_code in (301, 302, 303, 307, 308):
                url = urllib.parse.urljoin(url, resp.headers.get("Location", ""))
                resp.close()
                continue
            if resp.status_code >= 400:
                resp.close()
                return "", f"HTTP {resp.status_code}"
            cl = int(resp.headers.get("Content-Length") or 0)
            if cl > _MAX_GEOTIFF_BYTES:
                resp.close()
                return "", f"File too large ({cl // 1024 // 1024} MB; limit 50 MB)"
            data = bytearray()
            try:
                for chunk in resp.iter_content(65536):
                    data.extend(chunk)
                    if len(data) > _MAX_GEOTIFF_BYTES:
                        return "", "File too large (>50 MB)"
            finally:
                resp.close()
            if bytes(data[:2]) not in (b"II", b"MM"):
                return "", f"Not a GeoTIFF ({bytes(data[:40])!r})"
            return base64.b64encode(bytes(data)).decode("ascii"), f"{len(data) // 1024} KB"
        return "", "too many redirects"


@lru_cache(maxsize=4)
def fetch_geotiff_b64(source: str) -> tuple[str, str]:
    """Fetch a GeoTIFF server-side; returns (base64, info) or ('', error).

    Runs in a thread so the MCP call always returns within _FETCH_TIMEOUT_S seconds.
    """
    result: list[tuple[str, str]] = []

    def _run():
        result.append(_download_geotiff(source))

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout=_FETCH_TIMEOUT_S)
    if not result:
        fetch_geotiff_b64.cache_clear()
        return "", f"Download timed out after {_FETCH_TIMEOUT_S}s"
    b64, info = result[0]
    if not b64:
        fetch_geotiff_b64.cache_clear()  # don't cache failures — let the next call retry
    return b64, info


# ----------------------------------------------------------------------------- helpers
def _json_for_script(data) -> str:
    """JSON that can't close its <script> element, whatever it contains."""
    return json.dumps(data).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


# ----------------------------------------------------------------------------- server-side GeoTIFF rendering
_VIRIDIS = np.array(
    [[68, 1, 84], [62, 73, 137], [38, 130, 142], [53, 183, 121], [253, 231, 37]],
    dtype=np.float32,
)


def _encode_png_rgba(rgba: np.ndarray) -> bytes:
    """Encode a uint8 H×W×4 RGBA array as PNG bytes (stdlib only — no PIL)."""
    h, w = rgba.shape[:2]

    def chunk(name: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(name + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + name + data + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)  # 8-bit RGBA
    rows = b"".join(b"\x00" + row.tobytes() for row in rgba)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(rows, 6))
        + chunk(b"IEND", b"")
    )


def _render_geotiff_png(b64: str) -> tuple[str, list[float], float, float, int, int]:
    """Decode GeoTIFF base64 → viridis RGBA PNG base64 + bbox + (vmin, vmax, W, H).

    Applies the colormap in Python so the browser only needs to display a PNG — no
    browser-side geotiff.js decoding, no large payload, no ArcGIS-key/CSP issues.
    """
    raw = base64.b64decode(b64)
    with _tifffile.TiffFile(io.BytesIO(raw)) as tif:
        page = tif.pages[0]
        data = page.asarray().astype(np.float32)
        tags = page.tags

        def _tag(name: str, code: int):
            try:
                return tags[name].value
            except (KeyError, AttributeError):
                pass
            try:
                return tags[code].value
            except (KeyError, AttributeError):
                return None

        tp  = _tag("ModelTiepointTag",   33922)
        ps  = _tag("ModelPixelScaleTag", 33550)
        mt  = _tag("ModelTransformation", 34264)
        nodata_raw = _tag("GDAL_NODATA", 42113)

        # Flatten to 2-D (H, W); take first band if multi-band.
        if data.ndim == 3:
            data = data[0]
        H, W = data.shape

        # ---- bbox + south-up detection (mirrors terra_map_runtime.js logic) ----
        # southUp = mt[5] > 0  OR  ps[1] < 0  (row 0 is the south edge)
        south_up = False
        if tp is not None and ps is not None:
            arr_tp = np.array(tp, dtype=float).ravel()[:6]  # [col, row, z, lon, lat, z]
            arr_ps = np.array(ps, dtype=float).ravel()[:3]  # [Sx, Sy, Sz]
            col0, row0, _, lon0, lat0, _ = arr_tp
            sx, sy = float(arr_ps[0]), float(arr_ps[1])
            sx_a, sy_a = abs(sx), abs(sy)
            west  = float(lon0 - col0 * sx_a)
            east  = float(west + W * sx_a)
            if sy < 0:                               # south-up: tiepoint is at SW corner
                south = float(lat0 - row0 * sy_a)
                north = float(south + H * sy_a)
                south_up = True
            else:                                    # north-up: tiepoint is at NW corner
                north = float(lat0 + row0 * sy_a)
                south = float(north - H * sy_a)
        elif mt is not None:
            # 4×4 homogeneous matrix (row-major, 16 elements):
            #   X = mt[0]*col + mt[1]*row + mt[3]
            #   Y = mt[4]*col + mt[5]*row + mt[7]
            arr_mt = np.array(mt, dtype=float).ravel()
            col_sx  = float(arr_mt[0])   # X per column
            row_dy  = float(arr_mt[5])   # Y per row  (>0 → south-up, <0 → north-up)
            origin_x = float(arr_mt[3])
            origin_y = float(arr_mt[7])
            west = min(origin_x, origin_x + W * col_sx)
            east = max(origin_x, origin_x + W * col_sx)
            if row_dy > 0:               # south-up: row 0 = south, Y increases northward
                south = origin_y
                north = origin_y + H * row_dy
                south_up = True
            else:                        # north-up: row 0 = north, Y decreases southward
                north = origin_y
                south = origin_y + H * row_dy
        else:
            west, south, east, north = -180.0, -90.0, 180.0, 90.0

        # ---- nodata masking ----
        nodata = None
        if nodata_raw is not None:
            try:
                nodata = float(nodata_raw)
            except (TypeError, ValueError):
                pass

        valid = np.isfinite(data)
        if nodata is not None:
            valid &= data != nodata
        # INT16_MIN (-32768) is a ubiquitous fill sentinel even without a GDAL_NODATA tag.
        valid &= data != -32768.0

        vals = data[valid]
        if vals.size == 0:
            raise ValueError("No valid pixels in GeoTIFF")
        vmin, vmax = float(vals.min()), float(vals.max())
        if vmax == vmin:
            vmax = vmin + 1.0

        t = np.clip((data - vmin) / (vmax - vmin), 0.0, 1.0)
        idx_f = t * (len(_VIRIDIS) - 1)
        idx_lo = np.clip(idx_f.astype(np.int32), 0, len(_VIRIDIS) - 2)
        frac = (idx_f - idx_lo)[..., None]
        rgb = (_VIRIDIS[idx_lo] + frac * (_VIRIDIS[idx_lo + 1] - _VIRIDIS[idx_lo])).astype(np.uint8)

        rgba = np.zeros((H, W, 4), dtype=np.uint8)
        rgba[..., :3] = rgb
        rgba[..., 3] = np.where(valid, 255, 0).astype(np.uint8)

        # Flip rows when stored south-up so PNG row 0 = north (matches drawImage expectation).
        if south_up:
            rgba = rgba[::-1, :, :]

        # Downsample to ≤ 360 rows × 720 cols to keep the embedded PNG small (~100-150 KB).
        k = max(1, H // 360, W // 720)
        if k > 1:
            rgba = rgba[::k, ::k]

    png_b64 = base64.b64encode(_encode_png_rgba(rgba)).decode("ascii")
    return png_b64, [west, south, east, north], vmin, vmax, W, H


# ----------------------------------------------------------------------------- simple tile map
def _fetch_gibs_wms(layer: str, date: str, west: float, south: float, east: float, north: float,
                    width: int = 512) -> tuple[str, str]:
    """Fetch a GIBS WMS image server-side; return (base64_data, mime_type) or ('', error_msg)."""
    _, _, fmt = GIBS_LAYERS[layer]
    mime = "image/jpeg" if fmt == "jpg" else "image/png"
    height = max(64, min(512, round(width * (north - south) / max(east - west, 0.001))))
    transparent = "" if fmt == "jpg" else "&TRANSPARENT=true"
    url = (
        "https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi"
        f"?SERVICE=WMS&REQUEST=GetMap&VERSION=1.1.1"
        f"&LAYERS={layer}&STYLES=&FORMAT={urllib.parse.quote(mime)}"
        f"{transparent}&WIDTH={width}&HEIGHT={height}"
        f"&SRS=EPSG:4326&BBOX={west},{south},{east},{north}&TIME={date}"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "viz-mock"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
        if raw[:4] == b'\x89PNG' or raw[:3] == b'\xff\xd8\xff':
            return base64.b64encode(raw).decode("ascii"), mime
        return "", f"WMS returned non-image ({len(raw)} bytes, starts: {raw[:20]!r})"
    except Exception as exc:
        return "", f"WMS fetch failed: {exc}"


@mcp.tool(app=MAP_APP)
def show_tile_map(
    title: str = "MUR Sea Surface Temperature - North Atlantic",
    gibs_layer: Literal[
        "GHRSST_L4_MUR_Sea_Surface_Temperature",
        "MODIS_Terra_CorrectedReflectance_TrueColor",
        "VIIRS_SNPP_CorrectedReflectance_TrueColor",
    ] = "GHRSST_L4_MUR_Sea_Surface_Temperature",
    date: str = "2024-06-15",
    west: float = -30.0,
    south: float = 25.0,
    east: float = 45.0,
    north: float = 70.0,
) -> ToolResult:
    """Show a terra-map with a GIBS layer fetched server-side and embedded.

    The GIBS WMS image is fetched in Python and embedded as base64, so no
    external image requests are made from the browser (avoids iframe CSP issues).
    gibs_layer: product id (default = MUR SST colormap).
    date: imagery date (YYYY-MM-DD).
    west/south/east/north: initial view in EPSG:4326.
    """
    label, _, _ = GIBS_LAYERS[gibs_layer]
    img_b64, img_info = _fetch_gibs_wms(gibs_layer, date, west, south, east, north)
    has_image = bool(img_b64)

    view_js  = _json_for_script([west, south, east, north])
    b64_js   = _json_for_script(img_b64)
    mime_js  = _json_for_script(img_info if has_image else "image/png")
    lbl_js   = _json_for_script(f"{label} ({date})")
    err_js   = _json_for_script(img_info if not has_image else "")

    page = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@nasa-terra/components@0.0.202/cdn/themes/horizon.css">
  <script type="module" src="https://cdn.jsdelivr.net/npm/@nasa-terra/components@0.0.202/cdn/terra-ui-components-autoloader.js"></script>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/ol@10/ol.css">
  <script src="https://cdn.jsdelivr.net/npm/ol@10/dist/ol.js"></script>
  <style>
    html, body {{ margin: 0; padding: 0; background: #1c1f26; font: 12px monospace; color: #cdd; }}
    #status {{ padding: 4px 8px; color: #aef; background: rgba(0,0,0,0.7); white-space: pre; }}
    #status.error {{ color: #f88; }}
    terra-map {{ display: block; width: 100%; height: 460px; }}
    #legend {{ padding: 4px 8px; background: rgba(0,0,0,0.6); display: none; }}
    #legend label {{ display: flex; align-items: center; gap: 6px; cursor: pointer; user-select: none; }}
  </style>
</head>
<body>
  <div id="status">Loading...</div>
  <terra-map id="map" show-mouse-coordinates></terra-map>
  <div id="legend"><label><input type="checkbox" id="toggle" checked> <span id="layer-name"></span></label></div>
  <script type="module">
    const st = document.getElementById('status');
    const ok  = msg => {{ st.textContent = 'OK: ' + msg; st.className = ''; }};
    const err = msg => {{ st.textContent = 'ERR: ' + msg; st.className = 'error'; }};

    window.addEventListener('error', e => err('JS error: ' + e.message));
    window.addEventListener('unhandledrejection', e => err('Unhandled: ' + e.reason));

    if (!window.ol) {{ err('OpenLayers failed to load'); throw new Error(); }}

    await customElements.whenDefined('terra-map');
    const el = document.getElementById('map');
    await el.updateComplete;
    if (typeof el.addLayer !== 'function') {{ err('terra-map has no addLayer'); throw new Error(); }}

    const [w, s, e, n] = {view_js};
    el.fitToExtent([w, Math.max(s, -85), e, Math.min(n, 85)], {{ projection: 'EPSG:4326', padding: [30,30,30,30] }});

    const b64 = {b64_js};
    if (!b64) {{ err('No GIBS image: ' + {err_js}); throw new Error(); }}

    // Decode embedded image into a Blob, then createImageBitmap — no img-src URL, no CSP issue.
    const bytes = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
    const bitmap = await createImageBitmap(new Blob([bytes], {{ type: {mime_js} }}));

    const [bw, bs, be, bn] = {view_js};
    const olLayer = new ol.layer.Image({{
      opacity: 0.9,
      source: new ol.source.ImageCanvas({{
        projection: 'EPSG:4326',
        ratio: 1,
        canvasFunction: (extent, _res, _pr, size) => {{
          const out = document.createElement('canvas');
          out.width = size[0]; out.height = size[1];
          const ctx = out.getContext('2d');
          const [x0, y0, x1, y1] = extent;
          const sx = size[0] / (x1 - x0), sy = size[1] / (y1 - y0);
          ctx.drawImage(bitmap, (bw - x0) * sx, (y1 - bn) * sy, (be - bw) * sx, (bn - bs) * sy);
          return out;
        }},
      }}),
    }});
    el.addLayer(olLayer, {{ name: 'gibs' }});

    const legend = document.getElementById('legend');
    document.getElementById('layer-name').textContent = {lbl_js};
    document.getElementById('toggle').addEventListener('change', e => olLayer.setVisible(e.target.checked));
    legend.style.display = 'block';
    ok('Layer added: ' + {lbl_js});
  </script>
</body>
</html>"""

    card = Card(children=[
        CardHeader(children=[
            CardTitle(title),
            CardDescription(f"{label} · GIBS WMS · {date}"),
        ]),
        CardContent(children=[Embed(html=page, width="100%", height="540px")]),
    ])
    note = img_info if not has_image else f"{label} ({date}), embedded WMS image"
    summary = f"Rendered a terra-map showing {label} (GIBS WMS, {date}). View: [{west}, {south}, {east}, {north}]. {note}"
    return ToolResult(
        content=[TextContent(type="text", text=summary)],
        structured_content=PrefabApp(title=title, view=card),
    )


# ----------------------------------------------------------------------------- geotiff map
@mcp.tool(app=MAP_APP)
def show_geotiff_map(
    title: str = "MUR Sea Surface Temperature - Harmony GeoTIFF",
    units: str = "K",
) -> ToolResult:
    """Show a terra-map with a GeoTIFF from Harmony rendered server-side.

    Fetches the GeoTIFF, applies the viridis colormap in Python, and embeds the result
    as a small RGBA PNG — no browser-side GeoTIFF decoding, no ArcGIS-key issues.
    Override the source URL with GEOTIFF_SOURCE env var.
    """
    source = os.environ.get("GEOTIFF_SOURCE", HARMONY_URL)
    tiff_b64, fetch_info = fetch_geotiff_b64(source)

    png_b64 = ""
    bbox = [-180.0, -90.0, 180.0, 90.0]
    vmin = vmax = 0.0
    orig_w = orig_h = 0
    render_err = ""
    if tiff_b64:
        try:
            png_b64, bbox, vmin, vmax, orig_w, orig_h = _render_geotiff_png(tiff_b64)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            render_err = str(exc)

    b64_js   = _json_for_script(png_b64)
    bbox_js  = _json_for_script(bbox)
    err_js   = _json_for_script(render_err or fetch_info)
    label_js = _json_for_script("MUR SST")
    range_js = _json_for_script(f"{vmin:.1f} – {vmax:.1f} {units}")
    ok_js    = _json_for_script(f"Rendered {orig_w}×{orig_h} px, {vmin:.1f}–{vmax:.1f} {units}")

    page = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@nasa-terra/components@0.0.202/cdn/themes/horizon.css">
  <script type="module" src="https://cdn.jsdelivr.net/npm/@nasa-terra/components@0.0.202/cdn/terra-ui-components-autoloader.js"></script>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/ol@10/ol.css">
  <script src="https://cdn.jsdelivr.net/npm/ol@10/dist/ol.js"></script>
  <style>
    html, body {{ margin: 0; padding: 0; background: #1c1f26; font: 12px monospace; color: #cdd; }}
    #status {{ padding: 4px 8px; color: #aef; background: rgba(0,0,0,0.7); white-space: pre; }}
    #status.error {{ color: #f88; }}
    terra-map {{ display: block; width: 100%; height: 460px; }}
    #legend {{ padding: 4px 8px; background: rgba(0,0,0,0.6); display: none; }}
    #legend label {{ display: flex; align-items: center; gap: 6px; cursor: pointer; user-select: none; }}
    #colorbar {{ height: 8px; width: 120px; border-radius: 2px; margin-left: 4px;
                 background: linear-gradient(to right,#440154,#3e4989,#26828e,#35b779,#fde725); }}
    #range {{ font-size: 11px; color: #aaa; margin-left: 4px; }}
  </style>
</head>
<body>
  <div id="status">Loading...</div>
  <terra-map id="map" show-mouse-coordinates></terra-map>
  <div id="legend">
    <label><input type="checkbox" id="toggle" checked> <span id="layer-name"></span></label>
    <div id="colorbar"></div>
    <div id="range"></div>
  </div>
  <script type="module">
(async () => {{
    const st = document.getElementById('status');
    const ok  = msg => {{ st.textContent = 'OK: ' + msg; st.className = ''; }};
    const err = msg => {{ st.textContent = 'ERR: ' + msg; st.className = 'error'; }};

    window.addEventListener('error', e => err('JS error: ' + e.message));
    window.addEventListener('unhandledrejection', e => err('Unhandled: ' + e.reason));

    if (!window.ol) {{ err('OpenLayers failed to load'); return; }}

    await customElements.whenDefined('terra-map');
    const el = document.getElementById('map');
    await el.updateComplete;
    if (typeof el.addLayer !== 'function') {{ err('terra-map has no addLayer'); return; }}

    const b64 = {b64_js};
    if (!b64) {{ err('Render failed: ' + {err_js}); return; }}

    const [bw, bs, be, bn] = {bbox_js};
    el.fitToExtent([bw, Math.max(bs,-85), be, Math.min(bn,85)], {{ projection:'EPSG:4326', padding:[30,30,30,30] }});

    // Decode server-rendered viridis PNG — no geotiff.js needed in the browser.
    const bytes = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
    const bitmap = await createImageBitmap(new Blob([bytes], {{ type: 'image/png' }}));

    const olLayer = new ol.layer.Image({{
      opacity: 0.85,
      source: new ol.source.ImageCanvas({{
        projection: 'EPSG:4326',
        ratio: 1,
        canvasFunction: (extent, _r, _p, size) => {{
          const out = document.createElement('canvas');
          out.width = size[0]; out.height = size[1];
          const ctx = out.getContext('2d');
          const [x0, y0, x1, y1] = extent;
          const sx = size[0]/(x1-x0), sy = size[1]/(y1-y0);
          ctx.drawImage(bitmap, (bw-x0)*sx, (y1-bn)*sy, (be-bw)*sx, (bn-bs)*sy);
          return out;
        }},
      }}),
    }});
    el.addLayer(olLayer, {{ name: 'geotiff' }});

    document.getElementById('layer-name').textContent = {label_js};
    document.getElementById('range').textContent = {range_js};
    document.getElementById('toggle').addEventListener('change', e => olLayer.setVisible(e.target.checked));
    document.getElementById('legend').style.display = 'block';
    ok({ok_js});
}})();
  </script>
</body>
</html>"""

    global _geotiff_iframe_html
    _geotiff_iframe_html = page

    card = Card(children=[
        CardHeader(children=[
            CardTitle(title),
            CardDescription(f"Harmony GeoTIFF · viridis colormap · {units}"),
        ]),
        CardContent(children=[Embed(html=page, width="100%", height="530px")]),
    ])

    if not png_b64:
        summary = f"GeoTIFF fetch/render failed: {render_err or fetch_info}. Map without data layer."
    else:
        summary = (f"Rendered terra-map with MUR SST GeoTIFF (server-side viridis PNG, {orig_w}×{orig_h} px). "
                   f"Range: {vmin:.1f}–{vmax:.1f} {units}. Layer has a visibility toggle.")
    return ToolResult(
        content=[TextContent(type="text", text=summary)],
        structured_content=PrefabApp(title=title, view=card),
    )


# ----------------------------------------------------------------------------- chart card
# Mock numbers for the demo: plausible-looking daily anomalies, not real measurements.
# (Anomalies rather than absolute K: Prefab's line chart axis starts at 0, which would
# flatten 288-291 K into a straight line.)
MOCK_DAYS = [f"Jun {d}" for d in range(1, 31)]
MOCK_2024 = [round(0.62 + 0.012 * d + 0.08 * (((d * 7) % 5) - 2), 2) for d in range(30)]
MOCK_2023 = [round(0.35 + 0.035 * d + 0.06 * (((d * 3) % 4) - 1.5), 2) for d in range(30)]


def build_chart(title: str):
    rows = [{"day": day, "2024": a, "2023": b} for day, a, b in zip(MOCK_DAYS, MOCK_2024, MOCK_2023)]
    return Card(children=[
        CardHeader(children=[CardTitle(title),
                             CardDescription("Daily SST anomaly vs. 1991-2020, North Atlantic (°C) · mock data")]),
        CardContent(children=[
            LineChart(data=rows, x_axis="day", height=320, curve="smooth",
                      series=[ChartSeries(data_key="2024", label="June 2024"),
                              ChartSeries(data_key="2023", label="June 2023")]),
            Markdown(content="> Mock numbers for a UI demo, not measurements."),
        ]),
    ])


@mcp.tool(app=True)
def show_chart(title: str = "North Atlantic SST anomaly, June") -> ToolResult:
    """Show a line chart card (mock daily SST anomalies for June 2024 vs June 2023)."""
    summary = (f"Rendered a line chart for the user: {title}. Two series (June 2024, June 2023), "
               "30 days each. The values are mock data for a demo.")
    return ToolResult(content=[TextContent(type="text", text=summary)],
                      structured_content=PrefabApp(title=title, view=build_chart(title)))


# ----------------------------------------------------------------------------- run
if __name__ == "__main__":
    if "--preview" in sys.argv:
        (HERE / "chart_card.html").write_text(
            PrefabApp(title="Chart", view=build_chart("North Atlantic SST anomaly, June")).html(), encoding="utf-8")
        print(f"Wrote {HERE / 'chart_card.html'}")
    elif "--preview-geotiff" in sys.argv:
        import webbrowser
        show_geotiff_map()  # populates _geotiff_iframe_html as a side-effect
        out = HERE / "geotiff_card_preview.html"
        out.write_text(_geotiff_iframe_html, encoding="utf-8")
        print(f"Wrote {out}")
        if "--no-open" not in sys.argv:
            webbrowser.open(out.resolve().as_uri())
    else:
        mcp.run(transport="http", port=8765)
