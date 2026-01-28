"""
Collection metadata enrichment utilities.

Derives enriched_metadata from raw CMR UMM-C metadata by:
1. Copying all existing fields
2. Filling in missing fields where we can compute them (e.g., resolution from title)
"""

# pylint: disable=duplicate-code  # Intentional code patterns shared with util/spatial.py

import copy
import logging
import re
from typing import Any

# TODO: This import might need to move somewhere better
from tools.models.output_model import CollectionMatch
from util.spatial import parse_spatial_resolution_from_title
from util.temporal import parse_temporal_resolution_from_title

logger = logging.getLogger(__name__)


def enrich_collection_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """
    Create enriched version of UMM-C metadata with derived fields filled in.

    Args:
        metadata: Raw UMM-C metadata from CMR

    Returns:
        Enriched metadata (schema compliant) with computed fields
    """
    enriched = copy.deepcopy(metadata)

    # Enrich temporal resolution if missing
    _enrich_temporal_resolution(enriched)

    # Enrich spatial resolution if missing
    _enrich_spatial_resolution(enriched)

    return enriched


def _enrich_temporal_resolution(metadata: dict[str, Any]) -> None:
    """Enrich temporal resolution if missing, by parsing from title."""
    temporal_extents = metadata.get("TemporalExtents", [])

    # Check if any extent already has TemporalResolution
    has_resolution = any(extent.get("TemporalResolution") for extent in temporal_extents)

    if has_resolution:
        return

    # Try to extract from title
    title = metadata.get("EntryTitle", "")
    resolution = parse_temporal_resolution_from_title(title)

    if resolution and temporal_extents:
        # Add to first temporal extent
        temporal_extents[0]["TemporalResolution"] = resolution
    elif resolution:
        # Create temporal extent with resolution
        metadata["TemporalExtents"] = [{"TemporalResolution": resolution}]


def _enrich_spatial_resolution(metadata: dict[str, Any]) -> None:
    """Enrich spatial resolution if missing, by parsing from title."""
    spatial = metadata.setdefault("SpatialExtent", {})
    horiz = spatial.setdefault("HorizontalSpatialDomain", {})
    res_sys = horiz.setdefault("ResolutionAndCoordinateSystem", {})
    horiz_res = res_sys.get("HorizontalDataResolution", {})

    # Check if resolution already exists
    has_resolution = (
        horiz_res.get("VariesResolution")
        or horiz_res.get("PointResolution")
        or horiz_res.get("GriddedResolutions")
        or horiz_res.get("NonGriddedResolutions")
    )

    if has_resolution:
        return

    # Try to extract from title
    title = metadata.get("EntryTitle", "")
    resolution = parse_spatial_resolution_from_title(title)

    if resolution:
        res_sys["HorizontalDataResolution"] = {"GriddedResolutions": [resolution]}


def _parse_spatial_resolution_from_title(title: str) -> dict[str, Any] | None:  # pylint: disable=duplicate-code
    """
    Parse spatial resolution from collection title.

    Returns UMM-C compliant GriddedResolution object.
    """
    # Patterns: "1km", "250m", "0.25 degree", "500 m", "1 km"
    patterns = [
        (r"\b(\d+(?:\.\d+)?)\s*km\b", "Kilometers"),
        (r"\b(\d+(?:\.\d+)?)\s*m\b", "Meters"),
        (r"\b(\d+(?:\.\d+)?)\s*(?:deg|degree)s?\b", "Decimal Degrees"),
    ]

    for pattern, unit in patterns:
        match = re.search(pattern, title, re.IGNORECASE)
        if match:
            value = float(match.group(1))
            # Skip if it looks like a version number or year
            if 1900 < value < 2100:
                continue
            return {
                "XDimension": value,
                "YDimension": value,
                "Unit": unit,
            }

    return None


def filter_by_temporal_constraint(
    collections: list[CollectionMatch],
    start_date: Any | None,
    end_date: Any | None,
) -> list[CollectionMatch]:
    """
    Filter collections by temporal overlap with constraint.

    A collection is included if its temporal range overlaps with
    the constraint range.

    Args:
        collections: List of collection matches with temporal_coverage
        start_date: Constraint start date
        end_date: Constraint end date

    Returns:
        Filtered list of collections with temporal overlap
    """
    if start_date is None and end_date is None:
        return collections

    filtered = []

    for collection in collections:
        if collection.temporal_coverage is None:
            # No temporal info - include by default
            filtered.append(collection)
            continue

        cov = collection.temporal_coverage

        # Check for overlap
        # Overlap exists if: collection_start <= constraint_end AND collection_end >= constraint_start
        overlaps = True

        if start_date and cov.end_date and cov.end_date < start_date:
            # Collection must end after constraint starts
            overlaps = False

        if end_date and cov.start_date and cov.start_date > end_date:
            # Collection must start before constraint ends
            overlaps = False

        if overlaps:
            filtered.append(collection)

    return filtered


def filter_by_spatial_constraint(
    collections: list[CollectionMatch],
    wkt_geometry: str | None,
) -> list[CollectionMatch]:
    """
    Filter collections by spatial intersection with constraint.

    NOTE: Currently a stub - full implementation would require
    geometric intersection testing with collection bounding boxes.

    Args:
        collections: List of collection matches
        wkt_geometry: WKT geometry constraint

    Returns:
        Filtered list (currently returns all - needs implementation)

    TODO: Implement spatial filtering:
        1. Fetch SpatialExtent.HorizontalSpatialDomain.Geometry.BoundingRectangles from CMR
        2. Parse WKT geometry
        3. Test for intersection
    """
    if wkt_geometry is None:
        return collections

    # STUB: Return all collections until spatial filtering is implemented
    logger.warning(
        "Spatial filtering is not yet implemented - returning all %d collections",
        len(collections),
    )
    return collections
