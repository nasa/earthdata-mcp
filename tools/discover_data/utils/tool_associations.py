"""
Tool association enrichment for discover_data collections.

Enriches collections with UMM-T defined tool associations by checking CMR for tools
that can open or access each collection. URL templates are resolved with known values
(temporal range, spatial bounding box, collection concept ID) so the client receives
a ready-to-use link. Results are cached for 24 hours since UMM-T associations are
slow-moving.
"""

import contextvars
import hashlib
import logging
import math
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from urllib.parse import parse_qsl, quote, urlencode, urlparse, urlunparse

from langfuse import observe

from models.tools.discover_data import CollectionMatch, SpatialConstraint, TemporalConstraint
from util.cache import get_cache_client
from util.cmr.client import fetch_associations, fetch_collection_tags, fetch_tool_metadata

logger = logging.getLogger(__name__)


class ToolAssociationError(Exception):
    """Raised when any collection fails CMR tool association enrichment."""


TOOL_ASSOC_MAX_WORKERS = int(os.environ.get("TOOL_ASSOC_MAX_WORKERS", "10"))

# UMM-T associations are slow-moving — 24h TTL is safe
TOOL_ASSOC_CACHE_TTL = 86400

# Substring matched against topic (lower-cased) to identify visualisation tools
_VISUALIZATION_TOPIC_KEYWORD = "visualization"

# schema.org value type constants used in UMM-T QueryInput
_SCHEMA_START_DATE = "https://schema.org/startDate"
_SCHEMA_START_TIME = "https://schema.org/startTime"
_SCHEMA_END_DATE = "https://schema.org/endDate"
_SCHEMA_END_TIME = "https://schema.org/endTime"
_SCHEMA_INTERVAL = "https://schema.org/datasetTimeInterval"
_SCHEMA_BOX = "https://schema.org/box"
_CMR_CONCEPT_ID = "https://cmr.earthdata.nasa.gov/search/site/docs/search/api.html#c-concept-id"
_SCHEMA_SHORT_NAME = "shortName"

# Latitude thresholds for polar projection selection
_ARCTIC_LAT_THRESHOLD = 60.0
_ANTARCTIC_LAT_THRESHOLD = -60.0

# Base URLs for Earthdata Search and Worldview — used to generate guaranteed
# exploration links and to deduplicate against any CMR-defined tools that
# already reference the same applications.
_EARTHDATA_SEARCH_BASE = "https://search.earthdata.nasa.gov"
_WORLDVIEW_BASE = "https://worldview.earthdata.nasa.gov"
_DEDUP_BASE_URLS = frozenset({_EARTHDATA_SEARCH_BASE, _WORLDVIEW_BASE})

# Base layer appended after all GIBS product layers in both Worldview and CMR
# tool l= parameters (e.g. SOTO).  BlueMarble_NextGeneration is the standard
# GIBS base imagery and is used consistently across all link builders.
_WORLDVIEW_BASE_LAYER = "BlueMarble_NextGeneration"
_CMR_TOOL_BASE_LAYER = _WORLDVIEW_BASE_LAYER


def _preferred_projection(spatial: "SpatialConstraint | None") -> str:
    """
    Determine the best GIBS map projection for the given spatial extent.

    Classifies the extent as arctic, antarctic, or geographic based on latitude
    bounds. The thresholds (±60°) are stored as module constants for easy tuning.

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
    ``"<=2025-09-01T23:59:59Z"``.  This strips the leading comparison
    operator and parses the remaining ISO 8601 timestamp.

    Args:
        value: Constraint string from a GIBS tag ``match`` entry.

    Returns:
        Parsed ``datetime`` (timezone-aware), or ``None`` on parse failure.
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
    """
    Return True if a GIBS layer entry is valid for the given temporal context.

    A layer with no ``match`` key is always valid.  Otherwise the layer's
    valid window (``match.time_start`` / ``match.time_end``) is compared
    against the query's temporal range, or against ``collection_end_date``
    as a single-point fallback.  If neither is available all layers are
    considered valid.

    Args:
        entry: A single entry from the GIBS tag ``data`` list.
        temporal: Temporal constraint from the current search (optional).
        collection_end_date: Collection end date used when no query temporal
            is set — the layer must cover this point in time.

    Returns:
        ``True`` when the layer is valid for the temporal context.
    """
    match = entry.get("match")
    if not match:
        return True

    layer_start = _parse_gibs_match_dt(match.get("time_start", ""))
    layer_end = _parse_gibs_match_dt(match.get("time_end", ""))

    # Determine the query window to test against
    if temporal and (temporal.start_date or temporal.end_date):
        q_start = temporal.start_date
        q_end = temporal.end_date
    elif collection_end_date is not None:
        q_start = q_end = collection_end_date
    else:
        return True  # no temporal context — include all layers

    # Overlap check: [q_start, q_end] ∩ [layer_start, layer_end] ≠ ∅
    # Use datetime min/max as open-ended sentinels
    _MIN = datetime(1, 1, 1, tzinfo=timezone.utc)
    _MAX = datetime(9999, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
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

    Layers are returned in priority order: preferred projection first, then
    geographic fallback (for polar extents).  Duplicate products are suppressed.
    Entries with a ``match`` temporal window are filtered so only layers valid
    for the given temporal context are included.

    Args:
        tags: Tags dict from CMR JSON endpoint (``items[0].tags``).
        spatial: Spatial constraint used to determine the preferred projection.
        temporal: Temporal constraint from the current search (optional).
        collection_end_date: Collection end date used as a fallback when no
            query temporal is set, to pick the correct layer variant.

    Returns:
        Ordered list of GIBS layer product strings.
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
    """
    Select the most appropriate GIBS layer product identifier from collection tags.

    Convenience wrapper around ``_all_gibs_layers`` that returns only the first
    (highest-priority) layer, or ``None`` when no suitable layer is found.

    Args:
        tags: Tags dict from CMR JSON endpoint (``items[0].tags``).
        spatial: Spatial constraint used to determine the preferred projection.

    Returns:
        GIBS layer product string, or ``None``.
    """
    layers = _all_gibs_layers(tags, spatial)
    return layers[0] if layers else None


def _cmr_tool_layers_param(gibs_layers: list[str]) -> str | None:
    """
    Build the ``{+layers}`` value for CMR tool URL templates (e.g. SOTO).

    Mirrors the Worldview layer convention: the first layer is active on load,
    subsequent layers are suffixed with ``(hidden)`` so they appear in the
    tool's layer picker without cluttering the initial view, and
    ``BlueMarble_NextGeneration`` is always appended as the base imagery layer.

    Args:
        gibs_layers: GIBS layer product identifiers, highest-priority first.

    Returns:
        Comma-separated layer string, or ``None`` when the list is empty
        (causes ``l=`` to be stripped from the URL by post-processing).
    """
    if not gibs_layers:
        return None
    first = gibs_layers[0]
    hidden = [f"{layer}(hidden)" for layer in gibs_layers[1:]]
    return ",".join([first] + hidden + [_CMR_TOOL_BASE_LAYER])


def _eds_query(params: list[tuple[str, str]]) -> str:
    """Build a query string keeping bracket characters in keys un-encoded."""
    return "&".join(f"{k}={quote(v, safe='')}" for k, v in params)


def _earthdata_search_link(
    concept_id: str,
    temporal: "TemporalConstraint | None" = None,
    spatial: "SpatialConstraint | None" = None,
    collection_end_date: datetime | None = None,
) -> dict:
    """
    Build a guaranteed Earthdata Search granule-search link for a collection.

    Includes temporal (``qt``), spatial bounding box (``sb[0]``), and map
    projection (``lat``, ``projection``, ``zoom``) parameters when the
    corresponding constraints are available.  Bracket-style keys such as
    ``pg[0][v]`` are kept un-encoded so Earthdata Search parses them correctly.

    When no query temporal constraint is set but the collection has a known end
    date (i.e. the collection is closed), ``qt=,end_date`` is added so EDS
    anchors its results to within the collection's active period rather than
    defaulting to today (which may return zero granules for ended datasets).

    Args:
        concept_id: CMR collection concept ID.
        temporal: Temporal constraint from the current search (optional).
        spatial: Spatial constraint from the current search (optional).
        collection_end_date: End date of the collection's temporal coverage.
            Used as ``qt=`` upper-bound fallback when no query temporal is set.

    Returns:
        Exploration link dict pointing to Earthdata Search filtered to this collection.
    """
    params: list[tuple[str, str]] = [("p", concept_id)]

    if temporal and (temporal.start_date or temporal.end_date):
        start_str = (
            temporal.start_date.strftime("%Y-%m-%dT%H:%M:%S.000Z") if temporal.start_date else ""
        )
        end_str = temporal.end_date.strftime("%Y-%m-%dT%H:%M:%S.999Z") if temporal.end_date else ""
        params.append(("qt", f"{start_str},{end_str}"))
    elif collection_end_date is not None:
        end_str = collection_end_date.strftime("%Y-%m-%dT%H:%M:%S.999Z")
        params.append(("qt", f",{end_str}"))

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


def _worldview_link(
    gibs_layers: list[str],
    temporal: "TemporalConstraint | None",
    spatial: "SpatialConstraint | None" = None,
    collection_end_date: datetime | None = None,
) -> dict:
    """
    Build a NASA Worldview exploration link pre-loaded with GIBS layers.

    All provided layers are included in the ``l`` parameter, comma-separated,
    with ``BlueMarble_NextGeneration`` always appended as a base layer.  When a spatial
    constraint is available the ``v`` (viewport) parameter is set to the
    bounding box so Worldview opens centred over the area of interest (geographic
    extents only — ``v`` is omitted for polar projections where lat/lon bbox
    coordinates do not map correctly).  If
    a temporal start date is available it is added as the ``t`` parameter
    using Worldview's dash-T date-time format (``YYYY-MM-DD-THH:MM:SSZ``).
    When the spatial extent is polar the ``p`` parameter is set to
    ``"arctic"`` or ``"antarctic"`` so Worldview opens in the appropriate
    polar projection; geographic extents omit ``p`` (the default).

    When no query ``start_date`` is available, ``collection_end_date`` is used
    as the ``t`` parameter so that Worldview opens at the last date the
    collection has data rather than defaulting to today (which may show nothing
    for closed collections).

    Args:
        gibs_layers: GIBS layer product identifiers (highest priority first).
        temporal: Temporal constraint from the current search (optional).
        spatial: Spatial constraint from the current search (optional).
        collection_end_date: End date of the collection's temporal coverage.
            Used as ``t=`` fallback when the query has no start date.

    Returns:
        Exploration link dict pointing to NASA Worldview.
    """
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
        # Worldview uses a non-standard dash before the time component
        params.append(("t", temporal.start_date.strftime("%Y-%m-%d-T%H:%M:%SZ")))
    elif collection_end_date is not None:
        params.append(("t", collection_end_date.strftime("%Y-%m-%d-T%H:%M:%SZ")))

    return {
        "name": "NASA Worldview",
        "url": f"{_WORLDVIEW_BASE}/?" + urlencode(params, quote_via=quote, safe="()"),
        "topic": "Data analysis and visualization",
    }


def _build_exploration_links(
    tools: list[dict],
    concept_id: str,
    temporal: TemporalConstraint | None,
    spatial: SpatialConstraint | None,
    short_name: str | None,
    gibs_layers: list[str],
    collection_end_date: datetime | None = None,
) -> list[dict]:
    """
    Build the full ordered exploration links list for a collection.

    Guaranteed links are prepended:
      1. Earthdata Search — always included.
      2. NASA Worldview — included when one or more GIBS layers are available.

    CMR-defined tools are then appended in prioritised order (visualization
    topics first, templates preferred over base-URL-only).  Any CMR tool
    whose ``base_url`` starts with an already-guaranteed application URL
    (Earthdata Search or Worldview) is skipped to avoid duplicates.

    Args:
        tools: Raw UMM-T tool dicts for this collection (un-prioritised).
        concept_id: CMR collection concept ID.
        temporal: Temporal constraint from the current search.
        spatial: Spatial constraint from the current search.
        short_name: Collection short name.
        gibs_layers: All GIBS layer product identifiers for this collection
            (highest-priority first).  Worldview is added when non-empty;
            the first layer is also passed to CMR tools such as SOTO.
        collection_end_date: End date of the collection's temporal coverage.
            Forwarded to ``_earthdata_search_link`` and ``_worldview_link``
            as a ``qt=`` / ``t=`` fallback when no query temporal is set.

    Returns:
        Ordered list of exploration link dicts with ``name``, ``url``, ``topic``.
    """
    links: list[dict] = [_earthdata_search_link(concept_id, temporal, spatial, collection_end_date)]

    if gibs_layers:
        links.append(_worldview_link(gibs_layers, temporal, spatial, collection_end_date))

    for tool in _prioritize_tools(tools):
        base = (tool.get("base_url") or "").rstrip("/")
        if any(base.startswith(d) for d in _DEDUP_BASE_URLS):
            continue
        links.append(
            _resolve_tool_url(
                tool, concept_id, temporal, spatial, short_name, gibs_layers=gibs_layers
            )
        )

    return links


def _cache_key(concept_id: str) -> str:
    """
    Build cache key for tool association result.

    Args:
        concept_id: CMR collection concept ID

    Returns:
        Cache key string
    """
    key_hash = hashlib.sha256(concept_id.encode()).hexdigest()
    return f"tool_associations:{concept_id}:{key_hash}"


def _bbox_from_wkt(wkt: str) -> str | None:
    """
    Extract a bounding box string from a WKT geometry.

    Returns the bounding box as ``west,south,east,north`` (comma-separated,
    no spaces) per the schema.org/box / OpenStreetMap Bounding Box convention.

    Args:
        wkt: WKT geometry string (POLYGON, POINT, etc.)

    Returns:
        Bounding box string, or None if coordinates cannot be extracted.
    """
    coords = re.findall(r"(-?\d+\.?\d*)\s+(-?\d+\.?\d*)", wkt)
    if not coords:
        return None
    lons = [float(c[0]) for c in coords]
    lats = [float(c[1]) for c in coords]
    return f"{min(lons)},{min(lats)},{max(lons)},{max(lats)}"


def _round_bbox(bbox: str, decimals: int = 5) -> str:
    """Round each coordinate in a ``west,south,east,north`` bbox string."""
    parts = [round(float(v), decimals) for v in bbox.split(",")]
    return ",".join(str(p) for p in parts)


def _map_center_zoom(bbox: str) -> tuple[float, float, float]:
    """
    Compute map center coordinates and a suitable zoom level from a bounding box.

    The zoom level is derived from the larger angular span of the box using
    ``zoom = log2(360 / max_span) + 1``.

    Args:
        bbox: Bounding box string in ``west,south,east,north`` order.

    Returns:
        Tuple of ``(center_lat, center_lon, zoom)`` as floats.
    """
    west, south, east, north = (float(v) for v in bbox.split(","))
    center_lat = (south + north) / 2.0
    center_lon = (west + east) / 2.0
    lon_span = east - west
    lat_span = north - south
    max_span = max(lon_span, lat_span, 0.001)  # guard against zero-area
    zoom = math.log2(360.0 / max_span) + 1.0
    return center_lat, center_lon, zoom


def _resolve_value(
    value_type: str | None,
    concept_id: str,
    temporal: TemporalConstraint | None,
    spatial: SpatialConstraint | None,
    short_name: str | None = None,
) -> str | None:
    """
    Map a UMM-T QueryInput ValueType to a concrete value from the search context.

    Args:
        value_type: The ValueType URI from the QueryInput (e.g. schema.org URL).
        concept_id: CMR collection concept ID.
        temporal: Temporal constraint from the current search.
        spatial: Spatial constraint from the current search.
        short_name: Collection short name from UMM-JSON (e.g. 'TRMM_3B42').

    Returns:
        The resolved string value, or None if no mapping exists.
    """
    if not value_type:
        return None

    if value_type in (_SCHEMA_START_DATE, _SCHEMA_START_TIME):
        return temporal.start_date.isoformat() if temporal and temporal.start_date else None

    if value_type in (_SCHEMA_END_DATE, _SCHEMA_END_TIME):
        return temporal.end_date.isoformat() if temporal and temporal.end_date else None

    if value_type == _SCHEMA_INTERVAL:
        if not temporal:
            return None
        start = temporal.start_date.isoformat() if temporal.start_date else ".."
        end = temporal.end_date.isoformat() if temporal.end_date else ".."
        return f"{start}/{end}"

    if value_type == _SCHEMA_BOX:
        return _bbox_from_wkt(spatial.wkt_geometry) if spatial and spatial.wkt_geometry else None

    if value_type == _CMR_CONCEPT_ID:
        return concept_id

    if value_type == _SCHEMA_SHORT_NAME:
        return short_name

    return None


def _strip_empty_query_params(url: str) -> str:
    """
    Remove query parameters whose value is the empty string after template expansion.

    For example ``https://example.com/?l=&t=2020-01-01`` becomes
    ``https://example.com/?t=2020-01-01``, and a URL whose every parameter
    was empty has its query string removed entirely.

    Args:
        url: URL string, potentially with empty-valued query parameters.

    Returns:
        Cleaned URL string.
    """
    parsed = urlparse(url)
    if not parsed.query:
        return url
    params = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if v]
    # Use quote_via=quote with safe=",() " so that commas and parentheses in
    # layer list values (e.g. l=LayerA,LayerB(hidden),BlueMarble_NextGeneration)
    # are not percent-encoded when the query string is reconstructed.
    return urlunparse(parsed._replace(query=urlencode(params, quote_via=quote, safe=",()")))


def _expand_url_template(template: str, values: dict[str, str]) -> str:
    """
    Expand a minimal subset of RFC 6570 URL templates.

    Handles the forms used in UMM-T PotentialAction targets:
    - ``{?var1,var2,...}`` — query-string expansion; emits only vars with
      known values and omits the ``?`` prefix entirely when nothing is known.
    - ``{+var}`` — reserved expansion; substitutes the value directly (no
      percent-encoding of reserved chars).  When the variable has no known
      value the placeholder expands to an empty string and the surrounding
      query parameter (e.g. ``t=``) is stripped by post-processing.
    - ``{var}`` — simple substitution; emits empty string for unknown vars.

    After all substitutions any query parameters with empty values are removed
    from the URL so callers never receive links like ``?l=&t=``.

    Args:
        template: RFC 6570 URL template string.
        values: Mapping of variable name → resolved value.

    Returns:
        Expanded URL string.
    """

    def _expand_query(match: re.Match) -> str:  # type: ignore[type-arg]
        names = [n.strip() for n in match.group(1).split(",")]
        params = [(n, values[n]) for n in names if values.get(n) is not None]
        return ("?" + urlencode(params)) if params else ""

    def _expand_simple(match: re.Match) -> str:  # type: ignore[type-arg]
        return values.get(match.group(1).strip()) or ""

    result = re.sub(r"\{\?([^}]+)\}", _expand_query, template)
    # {+var} reserved expansion — treat like simple substitution
    result = re.sub(r"\{\+([^}]+)\}", _expand_simple, result)
    result = re.sub(r"\{([^?+#/;.][^}]*)\}", _expand_simple, result)
    return _strip_empty_query_params(result)


def _resolve_tool_url(
    tool: dict,
    concept_id: str,
    temporal: TemporalConstraint | None,
    spatial: SpatialConstraint | None,
    short_name: str | None = None,
    gibs_layers: list[str] | None = None,
) -> dict:
    """
    Resolve a raw UMM-T tool dict into a ready-to-render link.

    Populates the URL template with any search-context values we know
    (temporal range, spatial bounding box, concept ID, collection short name,
    and GIBS layers).  Unknown or optional parameters are omitted gracefully
    via ``_strip_empty_query_params``.

    Args:
        tool: Raw tool dict with ``name``, ``url_template``, ``query_inputs``.
        concept_id: CMR collection concept ID.
        temporal: Temporal constraint for the current search.
        spatial: Spatial constraint for the current search.
        short_name: Collection short name from UMM-JSON (e.g. 'TRMM_3B42').
        gibs_layers: All GIBS layer product identifiers for ``{+layers}``
            expansion (highest-priority first).  The first layer is active;
            remaining layers are hidden; ``BlueMarble_NextGeneration`` is
            appended as the base layer.  When empty or ``None``, any ``l=``
            parameter is stripped from the final URL.

    Returns:
        Dict with ``name`` and ``url`` (the resolved link).
    """
    url_template = tool.get("url_template")
    base_url = tool.get("base_url")
    topic = tool.get("topic")
    query_inputs = tool.get("query_inputs") or []

    if not url_template:
        return {"name": tool.get("name"), "url": base_url, "topic": topic}

    values = {
        qi["value_name"]: _resolve_value(
            qi.get("value_type"), concept_id, temporal, spatial, short_name
        )
        for qi in query_inputs
        if qi.get("value_name")
    }
    # Build the full layer string for {+layers} (first visible, rest hidden,
    # BlueMarble_NextGeneration base); None → l= stripped by post-processing.
    values["layers"] = _cmr_tool_layers_param(gibs_layers or [])

    return {
        "name": tool.get("name"),
        "url": _expand_url_template(url_template, values),
        "topic": topic,
    }


def _prioritize_tools(tools: list[dict]) -> list[dict]:
    """
    Sort tools so the most useful exploration links come first.

    Ordering (highest to lowest priority):
    1. Topic contains "visualization" — directly relevant for data exploration.
    2. Has a URL template (SearchAction deep link) — pre-parameterised link.
    3. All others (base_url only, no context pre-fill).

    Args:
        tools: Raw tool dicts as returned by ``fetch_tool_metadata``.

    Returns:
        Sorted list of tool dicts.
    """

    def _sort_key(tool: dict) -> tuple:
        topic = (tool.get("topic") or "").lower()
        is_visualization = _VISUALIZATION_TOPIC_KEYWORD in topic
        has_template = tool.get("url_template") is not None
        # Lower tuple → higher priority (sort ascending)
        return (not is_visualization, not has_template)

    return sorted(tools, key=_sort_key)


@observe(name="fetch_tool_associations")
def _fetch_tool_associations(concept_id: str) -> list[dict]:
    """
    Fetch tool associations for a single collection from CMR.

    Makes two parallel CMR calls (associations + tags), then one sequential
    call to resolve UMM-T metadata for any tool IDs found.

    Args:
        concept_id: CMR collection concept ID

    Returns:
        Dict with ``tools`` (list of UMM-T tool dicts) and ``tags`` (CMR collection
        tags dict).  Both can be empty if the collection has no associations or tags.
    """
    # fetch_associations and fetch_collection_tags are independent — run in parallel
    with ThreadPoolExecutor(max_workers=2) as pool:
        assoc_future = pool.submit(fetch_associations, concept_id)
        tags_future = pool.submit(fetch_collection_tags, concept_id)
        associations = assoc_future.result()
        tags = tags_future.result()

    tool_ids = associations.get("tools", [])
    if not tool_ids:
        return {"tools": [], "tags": tags}

    return {"tools": fetch_tool_metadata(tool_ids), "tags": tags}


@observe(name="enrich_with_tool_associations")
def enrich_with_tool_associations(
    collections: list[CollectionMatch],
    temporal: TemporalConstraint | None = None,
    spatial: SpatialConstraint | None = None,
) -> list[CollectionMatch]:
    """
    Enrich collections with UMM-T tool associations, resolving URLs from context.

    Checks each collection for CMR-defined tools that can open or access its data.
    Each tool's URL template is expanded using the current temporal/spatial context
    and the collection's concept ID, so the client receives a ready-to-use link.
    Collections with no associated tools receive an empty list. Raw templates are
    cached for 24 hours; URL resolution happens at request time. Any failure raises
    ToolAssociationError immediately.

    Args:
        collections: List of collections to enrich.
        temporal: Temporal constraint from the current search (used to pre-fill dates).
        spatial: Spatial constraint from the current search (used to pre-fill bbox).

    Returns:
        The same list of collections with exploration_links populated.

    Raises:
        ToolAssociationError: If any collection fails tool association enrichment.
    """
    if not collections:
        return collections

    cache = get_cache_client()

    pending: dict = {}

    with ThreadPoolExecutor(max_workers=TOOL_ASSOC_MAX_WORKERS) as executor:
        for collection in collections:
            key = _cache_key(collection.concept_id)
            cached = cache.get(key)

            if cached is not None:
                tags = cached.get("tags", {})
                cov = collection.temporal_coverage
                gibs_layers = _all_gibs_layers(
                    tags,
                    spatial,
                    temporal=temporal,
                    collection_end_date=cov.end_date if cov else None,
                )
                collection.exploration_links = _build_exploration_links(
                    cached["tools"],
                    collection.concept_id,
                    temporal,
                    spatial,
                    collection.short_name,
                    gibs_layers,
                    collection_end_date=cov.end_date if cov else None,
                )
            else:
                ctx = contextvars.copy_context()
                task = executor.submit(
                    ctx.run,
                    _fetch_tool_associations,
                    collection.concept_id,
                )
                pending[task] = collection

        for task in as_completed(pending):
            collection = pending[task]
            try:
                result = task.result()
                tools = result["tools"]
                tags = result.get("tags", {})
                cov = collection.temporal_coverage
                gibs_layers = _all_gibs_layers(
                    tags,
                    spatial,
                    temporal=temporal,
                    collection_end_date=cov.end_date if cov else None,
                )
                collection.exploration_links = _build_exploration_links(
                    tools,
                    collection.concept_id,
                    temporal,
                    spatial,
                    collection.short_name,
                    gibs_layers,
                    collection_end_date=cov.end_date if cov else None,
                )

                key = _cache_key(collection.concept_id)
                cache.set(
                    key,
                    {"tools": tools, "tags": tags, "timestamp": time.time()},
                    ttl=TOOL_ASSOC_CACHE_TTL,
                )
            except Exception as exc:
                raise ToolAssociationError(
                    f"Failed to fetch tool associations for {collection.concept_id}"
                ) from exc

    return collections
