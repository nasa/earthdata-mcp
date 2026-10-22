"""Resolve a CMR collection to its GIBS imagery layers.

Uses the same source terra-map's `collection-id` attribute uses: the EDSC tag
`edsc.extra.serverless.gibs` on the collection, which lists each GIBS product
with its native resolution and tile format.
"""

from __future__ import annotations

import logging
from typing import Any

from util.cmr.client import fetch_collection_tags
from util.visualization.specs import GibsLayer

logger = logging.getLogger(__name__)

GIBS_TAG = "edsc.extra.serverless.gibs"

# GIBS' Web Mercator endpoint ties each layer to one GoogleMapsCompatible level
# by native resolution; the wrong level returns 400s rather than blank tiles.
# https://nasa-gibs.github.io/gibs-api-docs/map-library-usage/
WEB_MERCATOR_LEVEL_BY_RESOLUTION = {
    "2km": "GoogleMapsCompatible_Level6",
    "1km": "GoogleMapsCompatible_Level7",
    "500m": "GoogleMapsCompatible_Level8",
    "250m": "GoogleMapsCompatible_Level9",
}


def gibs_entries_from_tags(tags: dict[str, Any]) -> list[dict[str, Any]]:
    """The GIBS product list from a collection's tags dict."""
    data = (tags.get(GIBS_TAG) or {}).get("data") or []
    return [d for d in data if isinstance(d, dict) and d.get("product")]


def gibs_layers_from_entries(
    entries: list[dict[str, Any]],
    date: str = "default",
    max_layers: int = 3,
    day_night: str | None = None,
) -> list[GibsLayer]:
    """Build GibsLayer specs (Web Mercator) from GIBS tag entries.

    Only the first layer is visible; the rest are added hidden so the card
    stays readable when a collection publishes many variants.
    """
    if day_night:
        filtered = [
            e for e in entries if (e.get("match") or {}).get("day_night_flag") in (None, day_night)
        ]
        entries = filtered or entries

    layers: list[GibsLayer] = []
    for entry in entries:
        resolution = entry.get("geographic_resolution")
        matrix = WEB_MERCATOR_LEVEL_BY_RESOLUTION.get(resolution or "")
        if not matrix:
            logger.debug("Skipping GIBS product %s: no Web Mercator level for %r",
                         entry.get("product"), resolution)
            continue
        try:
            layers.append(
                GibsLayer(
                    name=f"gibs-{len(layers) + 1}",
                    title=entry.get("title") or entry["product"],
                    layer=entry["product"],
                    date=date,
                    tile_matrix_set=matrix,
                    format="png" if entry.get("format") == "png" else "jpg",
                    visible=not layers,
                )
            )
        except ValueError as exc:
            logger.warning("Skipping GIBS product %s: %s", entry.get("product"), exc)
        if len(layers) >= max_layers:
            break
    return layers


def gibs_layers_for_collection(
    collection_concept_id: str,
    date: str = "default",
    max_layers: int = 3,
    day_night: str | None = None,
) -> list[GibsLayer]:
    """CMR lookup + conversion. Returns [] when the collection has no GIBS products."""
    tags = fetch_collection_tags(collection_concept_id)
    return gibs_layers_from_entries(gibs_entries_from_tags(tags), date, max_layers, day_night)
