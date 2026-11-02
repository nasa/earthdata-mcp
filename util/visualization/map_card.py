"""MapSpec -> Prefab card with an embedded terra-map."""

from __future__ import annotations

import json
import re
from functools import cache
from pathlib import Path

from prefab_ui.components.card import (
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
)
from prefab_ui.components.embed import Embed
from prefab_ui.components.markdown import Markdown

from util.visualization import config
from util.visualization.specs import MapSpec

_ASSETS = Path(__file__).parent / "assets"
_PLACEHOLDER = re.compile(r"__([A-Z_]+)__")


@cache
def _asset(name: str) -> str:
    return (_ASSETS / name).read_text(encoding="utf-8")


def _layers_js(layers: list[dict]) -> str:
    """Generate the OL script block from raw JS layer expressions.

    Each layer dict must have a ``"js"`` key containing a valid OL layer
    constructor expression. It is inserted directly — callers are trusted.
    Optional ``"name"`` is passed as the second arg to addLayer.

    Use the builder functions in ``util.visualization.layers`` to construct
    layer dicts rather than writing the JS strings by hand.
    """
    stmts = [
        f"  el.addLayer(await {layer['js']}, {{name:{json.dumps(layer.get('name', 'layer'))},position:'top'}});"
        for layer in layers
        if layer.get("js")
    ]
    if not stmts:
        return ""
    body = "\n".join(stmts)
    return (
        f'<script src="{config.OL_JS}"></script>\n'
        f'<script type="module">\n'
        f"(async()=>{{\n"
        f"  await customElements.whenDefined('terra-map');\n"
        f"  const el=document.getElementById('terra-map');\n"
        f"  await el.updateComplete;\n"
        f"{body}\n"
        f"}})();\n"
        f"</script>"
    )


def map_html(spec: MapSpec) -> str:
    """Standalone HTML page for the terra-map (also usable outside Prefab for previews).
    Layers are added via JS after the map is initialized."""
    collection_attr = (
        f'collection-id="{spec.collection_id}"' if spec.collection_id else ""
    )
    coords_attr = "show-mouse-coordinates" if spec.show_coordinates else ""
    values = {
        "TERRA_CSS": config.TERRA_CSS,
        "TERRA_AUTOLOADER": config.TERRA_AUTOLOADER,
        "HEIGHT": str(int(spec.height)),
        "COLLECTION_ATTR": collection_attr,
        "COORDS_ATTR": coords_attr,
        "LAYERS_JS": _layers_js(spec.layers),
    }
    return _PLACEHOLDER.sub(
        lambda m: values.get(m.group(1), m.group(0)), _asset("terra_map.html")
    )


def map_card(spec: MapSpec, extra_notes: list[str] | None = None) -> Card:
    """Prefab card: title, embedded terra-map, and optional caveats."""
    notes = [*spec.notes, *(extra_notes or [])]

    header = [CardTitle(spec.title)]
    if spec.subtitle:
        header.append(CardDescription(spec.subtitle))

    content: list = [
        Embed(html=map_html(spec), width="100%", height=f"{spec.height}px")
    ]
    if notes:
        footer = "\n".join(f"> {n}" for n in notes)
        content.append(Markdown(content=footer))

    return Card(children=[CardHeader(children=header), CardContent(children=content)])
