"""Shared helpers for the lightweight CMR search MCP tools."""

import json
import logging
from datetime import datetime
from io import BytesIO
from typing import Any

from shapely import make_valid, orient_polygons
from shapely import wkt as shapely_wkt
from shapely.errors import GEOSException
from shapely.geometry import mapping

from util.temporal import extract_temporal_extent, parse_iso_datetime

logger = logging.getLogger(__name__)


def format_cloud_cover_range(
    cloud_cover_min: float | None,
    cloud_cover_max: float | None,
) -> str | None:
    """Format a CMR cloud_cover range parameter.

    CMR expects ``cloud_cover=min,max`` where both bounds are in [0, 100].
    Either bound may be omitted (e.g. ``,20`` means 0–20, ``80,`` means 80–100).
    Returns *None* when neither bound is supplied.
    """
    if cloud_cover_min is None and cloud_cover_max is None:
        return None

    min_str = (
        ""
        if cloud_cover_min is None
        else str(
            int(cloud_cover_min) if cloud_cover_min == int(cloud_cover_min) else cloud_cover_min
        )
    )
    max_str = (
        ""
        if cloud_cover_max is None
        else str(
            int(cloud_cover_max) if cloud_cover_max == int(cloud_cover_max) else cloud_cover_max
        )
    )
    return f"{min_str},{max_str}"


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

    concept_id = meta.get("concept-id", "")
    logger.debug("Normalizing collection record: %s", concept_id)

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

    related_list = umm.get("RelatedUrls")
    if not isinstance(related_list, list):
        related_list = []

    related_urls = [
        {
            "url": url_item.get("URL"),
            "type": url_item.get("Type"),
            "subtype": url_item.get("Subtype"),
            "description": url_item.get("Description"),
        }
        for url_item in related_list
        if isinstance(url_item, dict) and url_item.get("URL")
    ]

    return {
        "concept_id": concept_id,
        "native_id": meta.get("native-id"),
        "revision_id": meta.get("revision-id"),
        "provider_id": meta.get("provider-id"),
        "short_name": umm.get("ShortName"),
        "version": str(version) if version is not None else None,
        "entry_title": umm.get("EntryTitle") or umm.get("ShortName") or meta.get("concept-id", ""),
        "abstract": umm.get("Abstract"),
        "time_start": start_date,
        "time_end": end_date,
        "is_ongoing": is_ongoing,
        "platforms": _dedupe_strings(platforms),
        "instruments": _dedupe_strings(instruments),
        "processing_level_id": umm.get("ProcessingLevel").get("Id")
        if isinstance(umm.get("ProcessingLevel"), dict)
        else None,
        "doi": umm.get("DOI").get("DOI") if isinstance(umm.get("DOI"), dict) else None,
        "collection_data_type": umm.get("CollectionDataType"),
        "temporal_resolution": _extract_collection_temporal_resolution(umm),
        "spatial_resolution": _extract_collection_spatial_resolution(umm),
        "related_urls": related_urls,
    }


def normalize_granule_item(item: dict[str, Any]) -> dict[str, Any]:
    """Normalize a CMR UMM granule item into the MCP-facing response shape."""
    meta = item.get("meta", {})
    umm = item.get("umm", {})

    concept_id = meta.get("concept-id", "")
    logger.debug("Normalizing granule record: %s", concept_id)

    time_start, time_end = extract_granule_temporal_extent(umm)

    size_mb, data_format = _extract_granule_archive_info(umm)

    parent_coll = umm.get("ParentCollection")
    data_granule = umm.get("DataGranule")

    return {
        "concept_id": concept_id,
        "native_id": meta.get("native-id"),
        "revision_id": meta.get("revision-id"),
        "provider_id": meta.get("provider-id"),
        "collection_concept_id": (
            meta.get("parent-collection-id")
            or umm.get("CollectionConceptId")
            or (parent_coll.get("CollectionConceptId") if isinstance(parent_coll, dict) else None)
        ),
        "granule_ur": umm.get("GranuleUR") or meta.get("native-id") or meta.get("concept-id", ""),
        "producer_granule_id": umm.get("ProducerGranuleId"),
        "time_start": time_start,
        "time_end": time_end,
        "cloud_cover": umm.get("CloudCover"),
        "day_night_flag": data_granule.get("DayNightFlag")
        if isinstance(data_granule, dict)
        else None,
        "size_mb": size_mb,
        "data_format": data_format,
        "bounding_box": _extract_granule_bounding_box(umm),
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


def normalize_tool_item(item: dict[str, Any]) -> dict[str, Any]:
    """Normalize a CMR UMM tool item into the MCP-facing response shape."""
    meta = item.get("meta", {})
    umm = item.get("umm", {})

    concept_id = meta.get("concept-id", "")
    logger.debug("Normalizing tool record: %s", concept_id)

    return {
        "concept_id": concept_id,
        "native_id": meta.get("native-id"),
        "revision_id": meta.get("revision-id"),
        "provider_id": meta.get("provider-id"),
        "name": umm.get("Name"),
        "long_name": umm.get("LongName"),
        "type": umm.get("Type"),
        "version": umm.get("Version"),
        "description": umm.get("Description"),
        "url": umm.get("URL"),
        "doi": umm.get("DOI"),
        "related_urls": umm.get("RelatedURLs"),
        "supported_input_formats": umm.get("SupportedInputFormats"),
        "supported_output_formats": umm.get("SupportedOutputFormats"),
        "supported_operating_systems": umm.get("SupportedOperatingSystems"),
        "supported_browsers": umm.get("SupportedBrowsers"),
        "supported_software_languages": umm.get("SupportedSoftwareLanguages"),
        "tool_keywords": umm.get("ToolKeywords"),
        "organizations": umm.get("Organizations"),
        "quality": umm.get("Quality"),
        "access_constraints": umm.get("AccessConstraints"),
        "use_constraints": umm.get("UseConstraints"),
        "potential_action": umm.get("PotentialAction"),
    }


def normalize_service_item(item: dict[str, Any]) -> dict[str, Any]:
    """Normalize a CMR UMM service item into the MCP-facing response shape."""
    meta = item.get("meta", {})
    umm = item.get("umm", {})

    concept_id = meta.get("concept-id", "")
    logger.debug("Normalizing service record: %s", concept_id)

    return {
        "concept_id": concept_id,
        "native_id": meta.get("native-id"),
        "revision_id": meta.get("revision-id"),
        "provider_id": meta.get("provider-id"),
        "name": umm.get("Name"),
        "long_name": umm.get("LongName"),
        "type": umm.get("Type"),
        "version": umm.get("Version"),
        "description": umm.get("Description"),
        "url": umm.get("URL"),
        "related_urls": umm.get("RelatedURLs"),
        "access_constraints": umm.get("AccessConstraints"),
        "use_constraints": umm.get("UseConstraints"),
        "service_options": umm.get("ServiceOptions"),
        "operation_metadata": umm.get("OperationMetadata"),
    }


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


def _extract_collection_temporal_resolution(umm: dict[str, Any]) -> str | None:
    """Extract the first human-readable temporal resolution from UMM-C.

    Searches the TemporalExtents array for a defined resolution. Combines the numeric
    Value and Unit into a single string (e.g., "1 Day") for the LLM.
    Defensive type checking is required as CMR payloads occasionally deviate from schema.
    """
    extents = umm.get("TemporalExtents", [])
    # CMR sometimes returns a single string instead of a list of extents
    if not isinstance(extents, list):
        return None

    for extent in extents:
        # Ensure the extent item is actually a dictionary before calling .get()
        if not isinstance(extent, dict):
            continue

        # CMR sometimes uses an array "TemporalResolutions" or a single object "TemporalResolution"
        resolutions = extent.get("TemporalResolutions", [])
        if not resolutions:
            single_res = extent.get("TemporalResolution")
            if single_res:
                resolutions = [single_res]

        for res in resolutions:
            # Ensure the resolution item is a dictionary
            if not isinstance(res, dict):
                continue
            value = res.get("Value")
            unit = res.get("Unit")
            if value is not None and unit:
                return f"{value} {unit}"
    return None


def _extract_collection_spatial_resolution(umm: dict[str, Any]) -> str | None:
    """Extract the first human-readable spatial resolution from UMM-C.

    Deeply inspects the HorizontalSpatialDomain for gridded, non-gridded, or point resolutions.
    If X and Y dimensions exist, it combines them (e.g., "1000x1000 Meters").
    If only X exists, it returns a 1D string (e.g., "1000 Meters").
    """
    spatial_extent = umm.get("SpatialExtent", {})
    # Prevent AttributeError if CMR returns a list or string instead of a dict
    if not isinstance(spatial_extent, dict):
        return None

    domain = spatial_extent.get("HorizontalSpatialDomain", {})
    # Ensure domain is a dict before deep traversal
    if not isinstance(domain, dict):
        return None

    resolution = domain.get("ResolutionAndCoordinateSystem", {})
    if not isinstance(resolution, dict):
        return None

    for res_type in ["HorizontalDataResolution", "VerticalDataResolution"]:
        for key in [
            "GriddedResolutions",
            "NonGriddedResolutions",
            "PointResolution",
            "GenericResolutions",
        ]:
            res_container = resolution.get(res_type, {})
            # Ensure the resolution type container is a dict
            if not isinstance(res_container, dict):
                continue

            res_list = res_container.get(key, [])
            if res_list:
                # CMR schema allows either a list of resolutions or a single object
                item = res_list[0] if isinstance(res_list, list) else res_list
                # Ensure the extracted item is a dict before calling .get()
                if not isinstance(item, dict):
                    continue

                x = item.get("XDimension")
                y = item.get("YDimension")
                unit = item.get("Unit")
                if x is not None and y is not None and unit:
                    return f"{x}x{y} {unit}"
                if x is not None and unit:
                    return f"{x} {unit}"
    return None


def _extract_granule_archive_info(umm: dict[str, Any]) -> tuple[float | None, str | None]:
    """Extract the size in MB and data format from UMM-G.

    Pulls the first available ArchiveAndDistributionInformation entry. Converts raw bytes
    into Megabytes so the LLM can more easily interpret and communicate file sizes.
    """
    granule = umm.get("DataGranule")
    # Ensure DataGranule is a dict (CMR sometimes omits it entirely or uses null)
    if not isinstance(granule, dict):
        return None, None

    archive_info = granule.get("ArchiveAndDistributionInformation", [])
    # Ensure the distribution info is a list before iterating
    if not isinstance(archive_info, list):
        return None, None

    for info in archive_info:
        # Ensure the info item is a dictionary before extracting size/format
        if not isinstance(info, dict):
            continue
        size = info.get("SizeInBytes")
        fmt = info.get("Format")
        try:
            # Safely cast size to float in case CMR returned it as a string
            size_mb = round(float(size) / (1024 * 1024), 2) if size is not None else None
        except (ValueError, TypeError):
            size_mb = None

        if size_mb is not None or fmt is not None:
            return size_mb, fmt
    return None, None


def _extract_granule_bounding_box(umm: dict[str, Any]) -> list[float] | None:
    """Extract the Minimum Bounding Rectangle (MBR) as [West, South, East, North] from UMM-G.

    Aggregates all valid bounding rectangles into a single MBR. For swathes or irregular
    polygons, this MBR fully encloses the data but may contain empty space at the corners.
    The 4-element array format provides a lightweight geospatial context for the LLM.
    """
    extent = umm.get("SpatialExtent", {})
    # Prevent AttributeError if CMR returns a list or string instead of a dict
    if not isinstance(extent, dict):
        return None

    domain = extent.get("HorizontalSpatialDomain", {})
    # Ensure domain is a dict before extracting geometry
    if not isinstance(domain, dict):
        return None

    geometries = domain.get("Geometry", {})
    # Ensure geometry is a dict before looking for bounding rectangles
    if not isinstance(geometries, dict):
        return None

    rects = geometries.get("BoundingRectangles", [])
    # Ensure BoundingRectangles is a list before iterating
    if not isinstance(rects, list):
        return None

    min_west, min_south, max_east, max_north = None, None, None, None

    for bbox in rects:
        # Ensure the individual bbox is a dictionary
        if not isinstance(bbox, dict):
            continue
        try:
            # Safely cast to float, catching TypeError if a value is None
            # or ValueError if a value is an un-parseable string
            w = float(bbox["WestBoundingCoordinate"])
            s = float(bbox["SouthBoundingCoordinate"])
            e = float(bbox["EastBoundingCoordinate"])
            n = float(bbox["NorthBoundingCoordinate"])

            min_west = min(min_west, w) if min_west is not None else w
            min_south = min(min_south, s) if min_south is not None else s
            max_east = max(max_east, e) if max_east is not None else e
            max_north = max(max_north, n) if max_north is not None else n
        except (KeyError, ValueError, TypeError):
            continue

    if min_west is not None:
        return [min_west, min_south, max_east, max_north]
    return None


def normalize_citation_item(item: dict[str, Any]) -> dict[str, Any]:
    """Normalize a CMR UMM citation item into the MCP-facing response shape."""
    meta = item.get("meta", {})
    umm = item.get("umm", {})

    concept_id = meta.get("concept-id", "")
    logger.debug("Normalizing citation record: %s", concept_id)

    associations = meta.get("associations") or {}

    return {
        "concept_id": concept_id,
        "native_id": meta.get("native-id"),
        "revision_id": meta.get("revision-id"),
        "provider_id": meta.get("provider-id"),
        "name": umm.get("Name"),
        "identifier": umm.get("Identifier"),
        "identifier_type": umm.get("IdentifierType"),
        "associated_collections": associations.get("collections") or [],
        "resolution_authority": umm.get("ResolutionAuthority"),
        "related_identifiers": umm.get("RelatedIdentifiers"),
        "abstract": umm.get("Abstract"),
        "citation_metadata": umm.get("CitationMetadata"),
        "metadata_specification": umm.get("MetadataSpecification"),
    }
