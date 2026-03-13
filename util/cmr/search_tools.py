"""Shared helpers for the lightweight CMR search MCP tools."""

import json
from datetime import datetime
from io import BytesIO
from typing import Any

from shapely import make_valid, orient_polygons
from shapely import wkt as shapely_wkt
from shapely.errors import GEOSException
from shapely.geometry import mapping

from util.temporal import extract_temporal_extent, parse_iso_datetime


def format_temporal_range(
    start_date: datetime | str | None,
    end_date: datetime | str | None,
) -> str | None:
    """Format a CMR temporal range using ISO 8601 timestamps with Z suffix."""
    if start_date is None and end_date is None:
        return None

    start_dt = _coerce_temporal_input(start_date, "temporal_start_date")
    end_dt = _coerce_temporal_input(end_date, "temporal_end_date")

    start_str = start_dt.isoformat().replace("+00:00", "Z") if start_dt is not None else ""
    end_str = end_dt.isoformat().replace("+00:00", "Z") if end_dt is not None else ""
    return f"{start_str},{end_str}"


def _coerce_temporal_input(value: datetime | str | None, field_name: str) -> datetime | None:
    """Normalize supported temporal input types for CMR temporal formatting."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        parsed = parse_iso_datetime(value)
        if parsed is None:
            raise ValueError(f"Invalid {field_name}: must be an ISO 8601 datetime")
        return parsed
    raise ValueError(f"Invalid {field_name}: must be an ISO 8601 datetime")


# CMR shapefile upload limits (https://cmr.earthdata.nasa.gov/search/site/docs/search/api.html)
_CMR_MAX_POINTS = 5_000
_CMR_MAX_BYTES = 1_000_000


def build_spatial_files(wkt_geometry: str | None) -> dict[str, Any] | None:
    """Convert WKT into the GeoJSON multipart payload accepted by CMR shapefile search.

    CMR limits: 1,000,000 bytes, 500 features, 5,000 points.
    Raises ValueError when the geometry exceeds these limits.
    """
    if not wkt_geometry:
        return None

    try:
        geometry = shapely_wkt.loads(wkt_geometry)
    except GEOSException as exc:
        raise ValueError(f"Invalid WKT geometry: {exc}") from exc
    if not geometry.is_valid:
        geometry = make_valid(geometry)
    geometry = _normalize_geometry_for_cmr(geometry)

    point_count = _count_geometry_points(geometry)
    if point_count > _CMR_MAX_POINTS:
        raise ValueError(
            f"Geometry has {point_count:,} points, exceeding the CMR shapefile limit of "
            f"{_CMR_MAX_POINTS:,}. Simplify the geometry before searching."
        )

    geojson = {
        "type": "FeatureCollection",
        "features": [{"type": "Feature", "geometry": mapping(geometry), "properties": {}}],
    }
    payload = json.dumps(geojson).encode("utf-8")

    if len(payload) > _CMR_MAX_BYTES:
        raise ValueError(
            f"Shapefile payload is {len(payload):,} bytes, exceeding the CMR limit of "
            f"{_CMR_MAX_BYTES:,} bytes. Simplify the geometry before searching."
        )

    return {"shapefile": ("shapefile", BytesIO(payload), "application/geo+json")}


def _count_geometry_points(geometry: Any) -> int:
    """Count total coordinate points in a Shapely geometry."""
    geom_type = geometry.geom_type
    if geom_type == "Point":
        return 1
    if geom_type in ("LineString", "LinearRing"):
        return len(geometry.coords)
    if geom_type == "Polygon":
        return len(geometry.exterior.coords) + sum(len(r.coords) for r in geometry.interiors)
    if geom_type in ("MultiPoint", "MultiLineString", "MultiPolygon", "GeometryCollection"):
        return sum(_count_geometry_points(g) for g in geometry.geoms)
    return 0


def _normalize_geometry_for_cmr(geometry: Any) -> Any:
    """Normalize polygon winding so CMR accepts uploaded GeoJSON geometry."""
    if geometry.geom_type in ("Polygon", "MultiPolygon"):
        return orient_polygons(geometry)
    return geometry


def normalize_collection_item(item: dict[str, Any]) -> dict[str, Any]:
    """Normalize a CMR UMM collection item into the MCP-facing response shape."""
    meta = item.get("meta", {})
    umm = item.get("umm", {})
    start_date, end_date, is_ongoing = extract_temporal_extent(umm)

    platforms: list[str] = []
    instruments: list[str] = []
    for platform in umm.get("Platforms") or []:
        platform_name = platform.get("ShortName")
        if platform_name:
            platforms.append(platform_name)

        for instrument in platform.get("Instruments") or []:
            instrument_name = instrument.get("ShortName")
            if instrument_name:
                instruments.append(instrument_name)

    version = umm.get("Version")

    return {
        "concept_id": meta.get("concept-id", ""),
        "short_name": umm.get("ShortName"),
        "version": str(version) if version is not None else None,
        "title": umm.get("EntryTitle") or umm.get("ShortName") or meta.get("concept-id", ""),
        "summary": umm.get("Abstract"),
        "time_start": start_date,
        "time_end": end_date,
        "is_ongoing": is_ongoing,
        "platforms": _dedupe_strings(platforms),
        "instruments": _dedupe_strings(instruments),
    }


def normalize_granule_item(item: dict[str, Any]) -> dict[str, Any]:
    """Normalize a CMR UMM granule item into the MCP-facing response shape."""
    meta = item.get("meta", {})
    umm = item.get("umm", {})
    time_start, time_end = extract_granule_temporal_extent(umm)

    return {
        "concept_id": meta.get("concept-id", ""),
        "collection_concept_id": (
            meta.get("parent-collection-id")
            or umm.get("CollectionConceptId")
            or umm.get("ParentCollection", {}).get("CollectionConceptId")
        ),
        "granule_ur": umm.get("GranuleUR") or meta.get("native-id") or meta.get("concept-id", ""),
        "producer_granule_id": umm.get("ProducerGranuleId"),
        "time_start": time_start,
        "time_end": time_end,
        "access_urls": extract_access_urls(umm),
    }


def extract_granule_temporal_extent(umm: dict[str, Any]) -> tuple[datetime | None, datetime | None]:
    """Extract temporal bounds from common UMM-G temporal shapes."""
    temporal_extent = umm.get("TemporalExtent") or {}

    range_date_time = temporal_extent.get("RangeDateTime")
    if isinstance(range_date_time, dict):
        return (
            parse_iso_datetime(range_date_time.get("BeginningDateTime", "")),
            parse_iso_datetime(range_date_time.get("EndingDateTime", "")),
        )

    range_date_times = temporal_extent.get("RangeDateTimes") or []
    starts: list[datetime] = []
    ends: list[datetime] = []
    for range_item in range_date_times:
        if begin := parse_iso_datetime(range_item.get("BeginningDateTime", "")):
            starts.append(begin)
        if end := parse_iso_datetime(range_item.get("EndingDateTime", "")):
            ends.append(end)

    return (min(starts) if starts else None, max(ends) if ends else None)


def extract_access_urls(umm: dict[str, Any]) -> list[str]:
    """Extract actionable URLs from OnlineAccessURLs and RelatedUrls."""
    urls: list[str] = []

    for entry in umm.get("OnlineAccessURLs") or []:
        if isinstance(entry, str):
            urls.append(entry)
        elif isinstance(entry, dict):
            url = entry.get("URL") or entry.get("URLValue")
            if url:
                urls.append(url)

    for entry in umm.get("RelatedUrls") or []:
        if not isinstance(entry, dict):
            continue

        url = entry.get("URL") or entry.get("URLValue")
        if not url:
            continue

        url_type = entry.get("Type") or ""
        content_type = entry.get("URLContentType") or ""
        if content_type == "DistributionURL" or url_type in {"GET DATA", "DOWNLOAD SOFTWARE"}:
            urls.append(url)

    return _dedupe_strings(urls)


def _dedupe_strings(values: list[str]) -> list[str]:
    """Preserve order while removing empty and duplicate string values."""
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
