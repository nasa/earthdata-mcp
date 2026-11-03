"""Builder functions for MapSpec.layers entries.

Each function returns a dict with ``"name"`` and ``"js"`` keys ready to
append to ``MapSpec.layers``.  The ``"js"`` value is a raw OL layer
constructor expression inserted directly into the map template.

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
    ext = json.dumps(extent)
    url_js = json.dumps(url)
    # Uses ImageCanvas (not ImageStatic) so the already-loaded <img> is drawn
    # directly to a canvas element — avoids the cross-origin canvas-taint issue
    # that silently blocks ImageStatic/ImageWMS from rendering inside terra-map.
    return {
        "name": name,
        "js": (
            f"(async()=>{{"
            f"const _src={url_js};"
            f"const _img=new Image();"
            # data: URIs are same-origin — load directly, no fetch needed (fetch('data:...')
            # is blocked in sandboxed iframes such as those used by MCP Jam).
            # External URLs use fetch()→blob to avoid cross-origin canvas taint.
            f"if(_src.startsWith('data:')){{await new Promise((r,x)=>{{_img.onload=r;_img.onerror=x;_img.src=_src;}});}}"
            f"else{{const _blob=await fetch(_src).then(r=>r.blob());const _burl=URL.createObjectURL(_blob);await new Promise((r,x)=>{{_img.onload=r;_img.onerror=x;_img.src=_burl;}});}}"
            f"const _ext=ol.proj.transformExtent({ext},'EPSG:4326','EPSG:3857');"
            f"return new ol.layer.Image({{"
            f"extent:_ext,opacity:{opacity},"
            f"source:new ol.source.ImageCanvas({{"
            f"canvasFunction:(_e,_r,pr,sz)=>{{"
            f"const c=document.createElement('canvas');"
            f"c.width=Math.round(sz[0]*pr);c.height=Math.round(sz[1]*pr);"
            f"c.getContext('2d').drawImage(_img,0,0,c.width,c.height);"
            f"return c;}},"
            f"projection:'EPSG:3857'"
            f"}})}})"
            f"}})()"
        ),
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
    url_js = json.dumps(url)
    params_js = json.dumps(params)
    ext_js = json.dumps(bbox)
    return {
        "name": name,
        "js": (
            f"(async()=>{{"
            f"const _ext4326={ext_js};"
            f"const _ext=ol.proj.transformExtent(_ext4326,'EPSG:4326','EPSG:3857');"
            f"const _p=new URLSearchParams({{SERVICE:'WMS',VERSION:'1.3.0',"
            f"REQUEST:'GetMap',CRS:'EPSG:3857',BBOX:_ext.join(','),"
            f"WIDTH:{img_size},HEIGHT:{img_size},...{params_js}}});"
            # fetch() → blob URL avoids canvas-taint and img.crossOrigin CORS failures.
            f"const _blob=await fetch({url_js}+'?'+_p.toString()).then(r=>r.blob());"
            f"const _burl=URL.createObjectURL(_blob);"
            f"const _img=new Image();"
            f"await new Promise((r,x)=>{{_img.onload=r;_img.onerror=x;_img.src=_burl;}});"
            f"return new ol.layer.Image({{extent:_ext,opacity:{opacity},"
            f"source:new ol.source.ImageCanvas({{"
            f"canvasFunction:(_e,_r,pr,sz)=>{{"
            f"const c=document.createElement('canvas');"
            f"c.width=Math.round(sz[0]*pr);c.height=Math.round(sz[1]*pr);"
            f"c.getContext('2d').drawImage(_img,0,0,c.width,c.height);return c;}},"
            f"projection:'EPSG:3857'}})}});"
            f"}})()"
        ),
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
        "js": (
            f"new ol.layer.Vector({{"
            f"source:new ol.source.Vector({{features:"
            f"{json.dumps(coords)}"
            f".map(c=>new ol.Feature({{geometry:new ol.geom.Point(ol.proj.fromLonLat(c))}}))}}),"
            f"style:new ol.style.Style({{image:new ol.style.Circle({{radius:{radius},"
            f"fill:new ol.style.Fill({{color:{json.dumps(color)}}}),"
            f"stroke:new ol.style.Stroke({{color:{json.dumps(stroke_color)},width:{stroke_width}}})"
            f"}})}})}})"
        ),
    }
