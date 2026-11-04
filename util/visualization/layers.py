"""Builder functions for MapSpec.layers entries.

Each function returns a dict with ``"name"`` and ``"js"`` keys ready to
append to ``MapSpec.layers``.  The ``"js"`` value is a raw OL layer
constructor expression inserted directly into the map template.

The JavaScript logic lives in ``util/visualization/js/``.  Python's only
job is to serialize parameters as a ``const _P = {...};`` line prepended to
the template file — no string interpolation of JS internals.

Example — combining layer types::

    from util.visualization import MapSpec, map_card
    from util.visualization.layers import image_layer, vector_layer, wms_layer

    spec = MapSpec(
        title="My Map",
        collection_id="C1374742240-LAADS",
        layers=[
            image_layer(png_data_uri, extent=[-10, 35, 40, 70], opacity=0.7, name="raster"),
            wms_layer("https://gibs.earthdata.nasa.gov/wms/epsg3857/best/wms.cgi",
                      "MODIS_Terra_Aerosol", name="aerosol"),
            vector_layer(coords, color="rgba(255,80,0,0.85)", name="points"),
        ],
    )
    card = map_card(spec)
"""

from __future__ import annotations

import json
from pathlib import Path

_JS_DIR = Path(__file__).parent / "js"


def _js(filename: str, params: dict) -> str:
    """Inject a _P params object inside the JS template at the // @PARAMS@ marker."""
    template = (_JS_DIR / filename).read_text(encoding="utf-8")
    return template.replace("// @PARAMS@\n", f"const _P={json.dumps(params)};\n", 1)


def image_layer(
    url: str,
    extent: list[float],
    *,
    opacity: float = 0.8,
    name: str = "layer",
) -> dict:
    """Georeferenced raster layer (PNG, base64 data URI, or remote URL).

    Args:
        url:     Image URL or ``data:image/png;base64,...`` string.
        extent:  ``[W, S, E, N]`` in EPSG:4326.
        opacity: 0–1.
        name:    Layer name passed to ``addLayer``.
    """
    return {
        "name": name,
        "js": _js("image_layer.js", {"url": url, "extent": extent, "opacity": opacity}),
    }


def wms_layer(  # pylint: disable=too-many-arguments
    url: str,
    layer_name: str,
    *,
    fmt: str = "image/png",
    bbox: list[float] | None = None,
    img_size: int = 1024,
    extra_params: dict | None = None,
    opacity: float = 0.9,
    name: str = "layer",
) -> dict:
    """WMS layer pre-fetched as a single georeferenced image.

    Fetches one WMS ``GetMap`` request (for ``bbox``) in an async IIFE, waits
    for the image to load, then creates a synchronous ``ImageCanvas`` layer.
    This mirrors ``image_layer``'s approach and avoids two terra-map pitfalls:

    * ``ol.source.TileWMS`` — tile URLs are rewritten through GITC proxy.
    * ``ol.source.ImageWMS`` — uses ``<img>`` + ``ctx.drawImage``, which is
      blocked by the cross-origin canvas-taint restriction inside terra-map.

    The pre-fetched image is a static snapshot; it does not re-request on
    pan/zoom.

    Args:
        url:          WMS endpoint URL.
        layer_name:   Value for the ``LAYERS`` WMS parameter.
        fmt:          ``FORMAT`` param (default ``image/png``).
        bbox:         ``[W, S, E, N]`` in EPSG:4326 for the GetMap request.
                      Defaults to global coverage ``[-180, -85, 180, 85]``.
        img_size:     Pixel width/height for the GetMap request (default 1024).
        extra_params: Any additional WMS params to merge in.
        opacity:      0–1.
        name:         Layer name passed to ``addLayer``.
    """
    if bbox is None:
        bbox = [-180, -85, 180, 85]
    params: dict = {"LAYERS": layer_name, "FORMAT": fmt, "TRANSPARENT": "TRUE"}
    if extra_params:
        params.update(extra_params)
    return {
        "name": name,
        "js": _js("wms_layer.js", {
            "url": url,
            "bbox": bbox,
            "img_size": img_size,
            "opacity": opacity,
            "params": params,
        }),
    }


def vector_layer(
    coords: list[list[float]],
    *,
    color: str = "rgba(255,80,0,0.85)",
    stroke_color: str = "#fff",
    radius: int = 6,
    stroke_width: float = 1.5,
    name: str = "layer",
) -> dict:
    """Vector point layer from a list of ``[lon, lat]`` coordinates (EPSG:4326).

    Args:
        coords:       ``[[lon, lat], ...]`` — fetched server-side and embedded as JSON.
        color:        Fill colour for each point circle.
        stroke_color: Stroke colour.
        radius:       Circle radius in pixels.
        stroke_width: Stroke width in pixels.
        name:         Layer name passed to ``addLayer``.
    """
    return {
        "name": name,
        "js": _js("vector_layer.js", {
            "coords": coords,
            "color": color,
            "stroke_color": stroke_color,
            "radius": radius,
            "stroke_width": stroke_width,
        }),
    }
