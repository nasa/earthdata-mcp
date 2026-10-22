"""MapSpec -> Prefab card with an embedded terra-map."""

from __future__ import annotations

import json
import re
from functools import cache
from pathlib import Path
from typing import Any

from prefab_ui.components.card import Card, CardContent, CardDescription, CardHeader, CardTitle
from prefab_ui.components.embed import Embed
from prefab_ui.components.markdown import Markdown

from util.visualization import config
from util.visualization.colormaps import colormap_rgb
from util.visualization.specs import FootprintLayer, GeoTiffLayer, GibsLayer, MapSpec

_ASSETS = Path(__file__).parent / "assets"
_PLACEHOLDER = re.compile(r"__([A-Z_]+)__")
# Draw order, bottom to top: imagery, data, outlines.
_LAYER_ORDER = {"gibs": 0, "geotiff": 1, "footprints": 2}


@cache
def _asset(name: str) -> str:
    return (_ASSETS / name).read_text(encoding="utf-8")


def json_for_script(data: Any) -> str:
    """JSON that is safe inside <script type="application/json">.

    Escaping <, > and & means no value can close the script element or open a
    comment, whatever the spec contains.
    """
    text = json.dumps(data, ensure_ascii=True, separators=(",", ":"), allow_nan=False)
    return text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def gibs_tile_url(layer: GibsLayer) -> str:
    """GIBS Web Mercator REST tile template for an OpenLayers XYZ source."""
    return (
        f"{config.GIBS_ORIGIN}/wmts/epsg3857/best/{layer.layer}/default/{layer.date}/"
        f"{layer.tile_matrix_set}/{{z}}/{{y}}/{{x}}.{layer.format}"
    )


def _layer_payload(layer: GeoTiffLayer | GibsLayer | FootprintLayer) -> dict[str, Any]:
    base = {
        "type": layer.type,
        "name": layer.name,
        "title": layer.title,
        "opacity": layer.opacity,
        "visible": layer.visible,
    }
    if isinstance(layer, GeoTiffLayer):
        scale = layer.value_scale
        return base | {
            "url": layer.url,
            "colors": colormap_rgb(layer.colormap, layer.reverse_colormap),
            "vmin": layer.vmin,
            "vmax": layer.vmax,
            "units": layer.units,
            "scale": scale.scale if scale else None,
            "offset": scale.offset if scale else None,
            "nodata": layer.nodata,
            "fit": layer.fit,
            "data": layer.data_b64,
        }
    if isinstance(layer, GibsLayer):
        payload = base | {"url": gibs_tile_url(layer), "maxZoom": layer.max_zoom}
        if layer.image_b64:
            payload["image"] = layer.image_b64
            payload["imageBbox"] = layer.image_bbox
            payload["imageFmt"] = layer.format
        return payload
    return base | {"boxes": layer.boxes, "color": layer.color}


def map_payload(spec: MapSpec) -> dict[str, Any]:
    """The JSON the browser runtime reads."""
    layers = sorted(spec.layers, key=lambda layer: _LAYER_ORDER[layer.type])
    return {
        "title": spec.title,
        "bounds": spec.initial_bounds(),
        "showCoordinates": spec.show_coordinates,
        "layers": [_layer_payload(layer) for layer in layers],
    }


def map_html(spec: MapSpec) -> str:
    """Standalone HTML page for the map (also usable outside Prefab, e.g. for previews)."""
    values = {
        "TERRA_CSS": config.TERRA_CSS,
        "TERRA_AUTOLOADER": config.TERRA_AUTOLOADER,
        "OL_JS": config.OL_JS,
        "OL_CSS": config.OL_JS.replace("/dist/ol.js", "/ol.css"),
        "GEOTIFF_JS": config.GEOTIFF_JS,
        "HEIGHT": str(int(spec.height)),
        "COORDS_ATTR": "show-mouse-coordinates" if spec.show_coordinates else "",
        "SPEC_JSON": json_for_script(map_payload(spec)),
        "RUNTIME_JS": _asset("terra_map_runtime.js"),
    }
    # Single pass, so substituted text is never re-scanned for placeholders.
    return _PLACEHOLDER.sub(lambda m: values.get(m.group(1), m.group(0)), _asset("terra_map.html"))


def describe_layers(spec: MapSpec) -> list[str]:
    """One line per layer, for the card footer and the model-facing summary."""
    lines = []
    for layer in spec.layers:
        label = layer.title or layer.name
        if isinstance(layer, GeoTiffLayer):
            rng = ""
            if layer.vmin is not None or layer.vmax is not None:
                rng = f", range {layer.vmin}–{layer.vmax}{' ' + layer.units if layer.units else ''}"
            lines.append(f"GeoTIFF **{label}** ({layer.colormap}{rng})")
        elif isinstance(layer, GibsLayer):
            lines.append(f"GIBS **{label}** (`{layer.layer}`, {layer.date})"
                         + ("" if layer.visible else ", hidden"))
        else:
            lines.append(f"Outlines **{label}** ({len(layer.boxes)} box{'es' if len(layer.boxes) != 1 else ''})")
    return lines


def map_card(spec: MapSpec, extra_notes: list[str] | None = None) -> Card:
    """Prefab card: title, embedded map, layer list and caveats."""
    notes = [*spec.notes, *(extra_notes or [])]
    footer = "\n".join(f"- {line}" for line in describe_layers(spec))
    if notes:
        footer += "\n\n" + "\n".join(f"> {n}" for n in notes)

    header = [CardTitle(spec.title)]
    if spec.subtitle:
        header.append(CardDescription(spec.subtitle))

    content = [Embed(html=map_html(spec), width="100%", height=f"{spec.height}px")]
    if footer:
        content.append(Markdown(content=footer))

    return Card(children=[CardHeader(children=header), CardContent(children=content)])
