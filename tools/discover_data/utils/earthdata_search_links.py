"""Earthdata Search link helpers for discover_data.

Temporal policy:
- ``qt`` is included only when user-extracted temporal constraints are present.
- No temporal fallback is inferred from collection metadata.
"""

from datetime import datetime
from typing import TYPE_CHECKING
from urllib.parse import quote

from util.geometry import _bbox_from_wkt, _map_center_zoom, _round_bbox

from .worldview_links import _preferred_projection

if TYPE_CHECKING:
    from models.tools.discover_data import SpatialConstraint, TemporalConstraint

_EARTHDATA_SEARCH_BASE = "https://search.earthdata.nasa.gov"


def _eds_query(params: list[tuple[str, str]]) -> str:
    """Build a query string keeping bracket characters in keys un-encoded."""
    return "&".join(f"{k}={quote(v, safe='')}" for k, v in params)


def _earthdata_search_link(
    concept_id: str,
    temporal: "TemporalConstraint | None" = None,
    spatial: "SpatialConstraint | None" = None,
    collection_end_date: datetime | None = None,
) -> dict:
    """Build a guaranteed Earthdata Search granule-search link for a collection.

    Temporal query parameter behavior intentionally follows user-provided context
    only. If no temporal constraint was extracted from the query, ``qt`` is
    omitted.
    """
    del collection_end_date
    params: list[tuple[str, str]] = [("p", concept_id)]

    if temporal and (temporal.start_date or temporal.end_date):
        start_str = (
            temporal.start_date.strftime("%Y-%m-%dT%H:%M:%S.000Z") if temporal.start_date else ""
        )
        end_str = temporal.end_date.strftime("%Y-%m-%dT%H:%M:%S.999Z") if temporal.end_date else ""
        params.append(("qt", f"{start_str},{end_str}"))

    if spatial and spatial.wkt_geometry:
        bbox = _bbox_from_wkt(spatial.wkt_geometry)
        if bbox:
            params.append(("sb[0]", _round_bbox(bbox)))

    projection = _preferred_projection(spatial)
    if projection == "arctic":
        params += [("lat", "90"), ("projection", "EPSG:3413"), ("zoom", "2")]
    elif projection == "antarctic":
        params += [("lat", "-90"), ("projection", "EPSG:3031"), ("zoom", "2")]
    elif spatial and spatial.wkt_geometry:
        bbox = _bbox_from_wkt(spatial.wkt_geometry)
        if bbox:
            clat, clon, zoom = _map_center_zoom(bbox)
            params += [("lat", str(clat)), ("long", str(clon)), ("zoom", str(zoom))]

    return {
        "name": "NASA Earthdata Search",
        "url": f"{_EARTHDATA_SEARCH_BASE}/search/granules?{_eds_query(params)}",
        "topic": "Data analysis and visualization",
    }
