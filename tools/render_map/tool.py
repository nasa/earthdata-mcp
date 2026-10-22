"""render_map: show GeoTIFFs, GIBS imagery and footprints on an interactive terra-map card."""

from __future__ import annotations

import logging

from fastmcp.server.dependencies import get_access_token
from fastmcp.tools.base import ToolResult
from langfuse import observe
from pydantic import ValidationError

from util.cmr.client import fetch_collection_tags
from util.langfuse import trace_update
from util.visualization import config
from util.visualization.builders import (
    footprints_layer,
    geotiff_layers_from_links,
    is_geotiff_url,
    parse_cmr_box,
)
from util.visualization.delivery import prepare_geotiff_layers
from util.visualization.gibs import (
    gibs_entries_from_tags,
    gibs_layers_from_entries,
)
from util.visualization.map_card import describe_layers, map_card
from util.visualization.result import error_result, ui_result
from util.visualization.specs import GibsLayer, MapSpec

logger = logging.getLogger(__name__)


def _boxes(granule_boxes: list[str | list[float]] | None) -> list[list[float]]:
    out = []
    for box in granule_boxes or []:
        out.append(parse_cmr_box(box) if isinstance(box, str) else [float(v) for v in box])
    return out


def _user_token() -> str | None:
    """The caller's EDL token, when the MCP request is authenticated."""
    try:
        access = get_access_token()
    except Exception:  # pylint: disable=broad-exception-caught
        return None
    return getattr(access, "token", None) or None


def _errors(exc: ValidationError) -> str:
    return "; ".join(f"{'.'.join(str(p) for p in e['loc']) or 'input'}: {e['msg']}" for e in exc.errors())


@observe(name="render_map")
def render_map(  # pylint: disable=too-many-arguments
    title: str,
    geotiff_urls: list[str] | None = None,
    units: str | None = None,
    colormap: str = "viridis",
    vmin: float | None = None,
    vmax: float | None = None,
    scale: float | None = None,
    offset: float | None = None,
    nodata: float | None = None,
    collection_concept_id: str | None = None,
    gibs_layers: list[str] | None = None,
    gibs_date: str = "default",
    bbox: list[float] | None = None,
    granule_boxes: list[str | list[float]] | None = None,
    subtitle: str | None = None,
) -> ToolResult:
    """Render an interactive map card for the user.

    Use after data tools have produced something to look at:
    - geotiff_urls: GeoTIFF links, e.g. the `links` from get_transformation_job_status for a
      job submitted with format="image/tiff". Non-.tif links are ignored. Each file becomes a
      colormapped layer; the first is shown and the view zooms to it.
      Harmony links are fetched by the server with the caller's Earthdata Login token, so the
      user must be signed in; small files are embedded in the card.
    - units / vmin / vmax / colormap: how to color the GeoTIFF, in physical units.
      If the file stores packed integers, pass scale and offset (physical = raw*scale + offset,
      from get_variables). Leave them unset for files that already hold physical values;
      scale/offset embedded in the file are used automatically.
    - collection_concept_id: adds the collection's GIBS imagery layers (looked up in CMR),
      for gibs_date (YYYY-MM-DD or "default" = latest).
    - gibs_layers: explicit GIBS layer ids to add instead of / in addition to the lookup.
    - bbox: [west, south, east, north] request area; drawn as an outline and used as the view.
    - granule_boxes: granule footprints, as CMR "S W N E" strings or [W, S, E, N] lists.

    Provide at least one of geotiff_urls, collection_concept_id, gibs_layers, bbox or
    granule_boxes. The model only receives a text summary of the map, not the pixels.
    """
    trace_update(
        tags=["visualization", "map"],
        metadata={
            "geotiff_count": len(geotiff_urls or []),
            "collection_concept_id": collection_concept_id,
            "gibs_layers": gibs_layers,
            "has_bbox": bbox is not None,
            "granule_box_count": len(granule_boxes or []),
        },
    )

    if not any([geotiff_urls, collection_concept_id, gibs_layers, bbox, granule_boxes]):
        return error_result(
            "Nothing to draw: pass geotiff_urls, collection_concept_id, gibs_layers, bbox or granule_boxes."
        )

    notes: list[str] = []
    try:
        layers: list = []

        # GIBS: tag lookup gives the right tile matrix/format per product.
        entries = []
        if collection_concept_id:
            entries = gibs_entries_from_tags(fetch_collection_tags(collection_concept_id))
            if not entries:
                notes.append(f"No GIBS imagery is tagged for {collection_concept_id}.")
        if gibs_layers:
            by_product = {e["product"]: e for e in entries}
            for i, layer_id in enumerate(gibs_layers):
                entry = by_product.get(layer_id)
                if entry:
                    built = gibs_layers_from_entries([entry], date=gibs_date, max_layers=1)
                    if built:
                        layers.append(built[0].model_copy(update={"name": f"gibs-x{i + 1}", "visible": i == 0}))
                        continue
                layers.append(GibsLayer(name=f"gibs-x{i + 1}", layer=layer_id, date=gibs_date, visible=i == 0))
                notes.append(f"GIBS layer {layer_id}: resolution unknown, assuming 250 m tiles (Level9, jpg).")
        elif entries:
            layers.extend(gibs_layers_from_entries(entries, date=gibs_date))

        links = geotiff_urls or []
        skipped = [u for u in links if not is_geotiff_url(u)]
        if skipped:
            notes.append(f"Ignored {len(skipped)} non-GeoTIFF link(s).")
        layers.extend(
            geotiff_layers_from_links(
                links, title=title, colormap=colormap, units=units, vmin=vmin, vmax=vmax,
                scale=scale, offset=offset, nodata=nodata,
            )
        )
        if links and not any(is_geotiff_url(u) for u in links):
            notes.append("No GeoTIFF links were provided; request format='image/tiff' from Harmony to map the data.")

        boxes = _boxes(granule_boxes)
        if boxes:
            layers.append(footprints_layer(boxes, name="granules", title="Granule footprints"))
        if bbox:
            layers.append(footprints_layer([bbox], name="request-area", title="Request area", color="#ffb000"))

        spec = MapSpec(title=title, subtitle=subtitle, layers=layers, bounds=bbox)
    except (ValidationError, ValueError) as exc:
        detail = _errors(exc) if isinstance(exc, ValidationError) else str(exc)
        logger.warning("render_map input rejected: %s", detail)
        return error_result(f"Could not build the map: {detail}")

    # Harmony links need Earthdata Login, which the map iframe can't do: fetch them here
    # with the caller's token and embed small files (larger ones get a presigned URL).
    spec, delivery_notes = prepare_geotiff_layers(spec, _user_token())
    notes.extend(delivery_notes)

    if not spec.layers:
        return error_result("Nothing to draw. " + " ".join(notes))

    # The iframe CSP is fixed at registration; flag data hosts it doesn't cover.
    blocked = config.unlisted_origins(spec.data_origins(), config.map_csp_domains()["connect_domains"])
    if blocked:
        notes.append(
            "These hosts are not in the map's allowed domains and will likely be blocked: "
            + ", ".join(blocked) + " (add them via VIZ_EXTRA_CONNECT_DOMAINS)."
        )

    summary = "\n".join(
        [f"Rendered an interactive map for the user: {title}", *[f"- {line.replace('**', '')}" for line in describe_layers(spec)]]
        + ([f"Notes: {' '.join(notes)}"] if notes else [])
        + ["The user can toggle layers and hover for values; describe the map in words, do not re-list URLs."]
    )
    return ui_result(map_card(spec, extra_notes=notes), summary, title=title)
