"""CMR UMM-derived tool-link helpers for discover_data.

Temporal policy:
- Temporal template values are resolved from user-extracted temporal
    constraints only.
- No temporal fallback is injected from collection metadata.
"""

import re
from urllib.parse import parse_qsl, quote, urlencode, urlparse, urlunparse

from models.tools.discover_data import SpatialConstraint, TemporalConstraint
from util.geometry import _bbox_from_wkt

from .worldview_links import _cmr_tool_layers_param

# Substring matched against topic (lower-cased) to identify visualisation tools
_VISUALIZATION_TOPIC_KEYWORD = "visualization"

# Base URLs for Earthdata Search and Worldview — used to generate guaranteed
# exploration links and to deduplicate against any CMR-defined tools that
# already reference the same applications.
_EARTHDATA_SEARCH_BASE = "https://search.earthdata.nasa.gov"
_WORLDVIEW_BASE = "https://worldview.earthdata.nasa.gov"
_DEDUP_BASE_URLS = frozenset({_EARTHDATA_SEARCH_BASE, _WORLDVIEW_BASE})

# schema.org value type constants used in UMM-T QueryInput
_SCHEMA_START_DATE = "https://schema.org/startDate"
_SCHEMA_START_TIME = "https://schema.org/startTime"
_SCHEMA_END_DATE = "https://schema.org/endDate"
_SCHEMA_END_TIME = "https://schema.org/endTime"
_SCHEMA_INTERVAL = "https://schema.org/datasetTimeInterval"
_SCHEMA_BOX = "https://schema.org/box"
_CMR_CONCEPT_ID = "https://cmr.earthdata.nasa.gov/search/site/docs/search/api.html#c-concept-id"
_SCHEMA_SHORT_NAME = "shortName"


def _resolve_value(  # pylint: disable=too-many-return-statements
    value_type: str | None,
    concept_id: str,
    temporal: TemporalConstraint | None,
    spatial: SpatialConstraint | None,
    short_name: str | None = None,
) -> str | None:
    """Map a UMM-T QueryInput ValueType to a concrete value from search context."""
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
    """Remove query params whose value is empty after template expansion."""
    parsed = urlparse(url)
    if not parsed.query:
        return url
    params = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if v]
    return urlunparse(parsed._replace(query=urlencode(params, quote_via=quote, safe=",()")))


def _expand_url_template(template: str, values: dict[str, str]) -> str:
    """Expand the RFC 6570 subset used by UMM-T PotentialAction targets."""

    def _expand_query(match: re.Match) -> str:  # type: ignore[type-arg]
        names = [n.strip() for n in match.group(1).split(",")]
        params = [(n, values[n]) for n in names if values.get(n) is not None]
        return ("?" + urlencode(params)) if params else ""

    def _expand_simple(match: re.Match) -> str:  # type: ignore[type-arg]
        return values.get(match.group(1).strip()) or ""

    result = re.sub(r"\{\?([^}]+)\}", _expand_query, template)
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
    """Resolve a raw UMM-T tool dict into a ready-to-render link."""
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
    values["layers"] = _cmr_tool_layers_param(gibs_layers or [])

    return {
        "name": tool.get("name"),
        "url": _expand_url_template(url_template, values),
        "topic": topic,
    }


def _prioritize_tools(tools: list[dict]) -> list[dict]:
    """Sort tools so visualization/template-first links come first."""

    def _sort_key(tool: dict) -> tuple:
        topic = (tool.get("topic") or "").lower()
        is_visualization = _VISUALIZATION_TOPIC_KEYWORD in topic
        has_template = tool.get("url_template") is not None
        return (not is_visualization, not has_template)

    return sorted(tools, key=_sort_key)
