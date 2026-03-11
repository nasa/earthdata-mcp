"""Worldview and GIBS-specific link helpers for discover_data.

Temporal policy:
- Prefer user-extracted temporal constraints when present.
- Fall back to collection end date for link time and layer matching when user
    temporal constraints are absent.

This fallback is intentional for usability because Worldview defaults to the
current day, which can otherwise land users on dates with no data.
"""

import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from urllib.parse import quote, urlencode

from util.geometry import _bbox_from_wkt

if TYPE_CHECKING:
    from models.tools.discover_data import SpatialConstraint, TemporalConstraint

# Latitude thresholds for polar projection selection
_ARCTIC_LAT_THRESHOLD = 60.0
_ANTARCTIC_LAT_THRESHOLD = -60.0

# Base URL for NASA Worldview link generation.
_WORLDVIEW_BASE = "https://worldview.earthdata.nasa.gov"

# Base layer appended after all GIBS product layers in both Worldview and CMR
# tool l= parameters (e.g. SOTO). BlueMarble_NextGeneration is the standard
# GIBS base imagery and is used consistently across all link builders.
_WORLDVIEW_BASE_LAYER = "BlueMarble_NextGeneration"
_CMR_TOOL_BASE_LAYER = _WORLDVIEW_BASE_LAYER


def _preferred_projection(spatial: "SpatialConstraint | None") -> str:
    """
    Determine the best GIBS map projection for the given spatial extent.

    Classifies the extent as arctic, antarctic, or geographic based on latitude
    bounds. The thresholds (+/-60 deg) are stored as module constants for easy tuning.

    Args:
        spatial: Spatial constraint from the current search, or None.

    Returns:
        One of ``"arctic"``, ``"antarctic"``, or ``"geographic"``.
    """
    if not spatial or not spatial.wkt_geometry:
        return "geographic"
    coords = re.findall(r"(-?\d+\.?\d*)\s+(-?\d+\.?\d*)", spatial.wkt_geometry)
    if not coords:
        return "geographic"
    lats = [float(c[1]) for c in coords]
    if min(lats) >= _ARCTIC_LAT_THRESHOLD:
        return "arctic"
    if max(lats) <= _ANTARCTIC_LAT_THRESHOLD:
        return "antarctic"
    return "geographic"


def _parse_gibs_match_dt(value: str) -> datetime | None:
    """
    Parse a GIBS ``match`` date-constraint string into a ``datetime``.

    GIBS match values look like ``">=2012-07-02T00:00:00Z"`` or
    ``"<=2025-09-01T23:59:59Z"``. This strips the leading comparison
    operator and parses the remaining ISO 8601 timestamp.
    """
    try:
        iso = re.sub(r"^[>=<!]+", "", value.strip())
        return datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def _gibs_entry_matches_temporal(
    entry: dict,
    temporal: "TemporalConstraint | None",
    collection_end_date: datetime | None,
) -> bool:
    """Return True if a GIBS layer entry is valid for the given temporal context."""
    match = entry.get("match")
    if not match:
        return True

    layer_start = _parse_gibs_match_dt(match.get("time_start", ""))
    layer_end = _parse_gibs_match_dt(match.get("time_end", ""))

    if temporal and (temporal.start_date or temporal.end_date):
        q_start = temporal.start_date
        q_end = temporal.end_date
    elif collection_end_date is not None:
        q_start = q_end = collection_end_date
    else:
        return True

    _MIN = datetime(1, 1, 1, tzinfo=UTC)
    _MAX = datetime(9999, 12, 31, 23, 59, 59, tzinfo=UTC)
    eff_layer_start = layer_start if layer_start is not None else _MIN
    eff_layer_end = layer_end if layer_end is not None else _MAX
    eff_q_start = q_start if q_start is not None else _MIN
    eff_q_end = q_end if q_end is not None else _MAX
    return eff_q_start <= eff_layer_end and eff_q_end >= eff_layer_start


def _all_gibs_layers(
    tags: dict,
    spatial: "SpatialConstraint | None",
    temporal: "TemporalConstraint | None" = None,
    collection_end_date: datetime | None = None,
) -> list[str]:
    """
    Return all GIBS layer product identifiers that support the preferred projection.
    """
    data = (tags.get("edsc.extra.serverless.gibs") or {}).get("data", [])
    if not data:
        return []
    projection = _preferred_projection(spatial)
    projections_to_try = [projection] if projection == "geographic" else [projection, "geographic"]
    layers: list[str] = []
    seen: set[str] = set()
    for proj in projections_to_try:
        for entry in data:
            if entry.get(proj) is True:
                if not _gibs_entry_matches_temporal(entry, temporal, collection_end_date):
                    continue
                product = entry.get("product")
                if product and product not in seen:
                    seen.add(product)
                    layers.append(product)
    return layers


def _best_gibs_layer(tags: dict, spatial: "SpatialConstraint | None") -> str | None:
    """Return the highest-priority GIBS layer, if any."""
    layers = _all_gibs_layers(tags, spatial)
    return layers[0] if layers else None


def _cmr_tool_layers_param(gibs_layers: list[str]) -> str | None:
    """Build the ``{+layers}`` value for CMR tool URL templates (e.g. SOTO)."""
    if not gibs_layers:
        return None
    first = gibs_layers[0]
    hidden = [f"{layer}(hidden)" for layer in gibs_layers[1:]]
    return ",".join([first] + hidden + [_CMR_TOOL_BASE_LAYER])


def _worldview_link(
    gibs_layers: list[str],
    temporal: "TemporalConstraint | None",
    spatial: "SpatialConstraint | None" = None,
    collection_end_date: datetime | None = None,
) -> dict:
    """Build a NASA Worldview exploration link pre-loaded with GIBS layers."""
    params: list[tuple[str, str]] = []

    projection = _preferred_projection(spatial)
    if projection in ("arctic", "antarctic"):
        params.append(("p", projection))

    if projection == "geographic" and spatial and spatial.wkt_geometry:
        bbox = _bbox_from_wkt(spatial.wkt_geometry)
        if bbox:
            params.append(("v", bbox))

    first = gibs_layers[0] if gibs_layers else None
    hidden = [f"{layer}(hidden)" for layer in gibs_layers[1:]]
    layer_list = ([first] if first else []) + hidden + [_WORLDVIEW_BASE_LAYER]
    params.append(("l", ",".join(layer_list)))

    if temporal and temporal.start_date:
        params.append(("t", temporal.start_date.strftime("%Y-%m-%d-T%H:%M:%SZ")))
    elif collection_end_date is not None:
        params.append(("t", collection_end_date.strftime("%Y-%m-%d-T%H:%M:%SZ")))

    return {
        "name": "NASA Worldview",
        "url": f"{_WORLDVIEW_BASE}/?" + urlencode(params, quote_via=quote, safe="(),"),
        "topic": "Data analysis and visualization",
    }
