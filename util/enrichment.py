"""
Collection metadata enrichment utilities.

Derives enriched_metadata from raw CMR UMM-C metadata by:
1. Copying all existing fields
2. Filling in missing fields where we can compute them (e.g., resolution from title)
"""

import copy
from typing import Any

from util.temporal import parse_temporal_resolution_from_title


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
