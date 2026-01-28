"""
Resolution parsing utilities for discover_data orchestrator.

Parses UMM-C metadata to extract temporal and spatial resolution information
for collection disambiguation.
"""

import re
from datetime import datetime
from typing import Any

from tools.models.output_model import ResolutionInfo, TemporalCoverage


def parse_temporal_resolution(umm_metadata: dict[str, Any]) -> tuple[str | None, float | None]:
    """
    Extract temporal resolution from UMM-C metadata.

    Checks multiple locations in the metadata:
    1. TemporalExtents[].TemporalResolution
    2. Title (common pattern: "Daily", "Monthly", "8-Day")

    Args:
        umm_metadata: UMM-C collection metadata

    Returns:
        Tuple of (human-readable resolution string, resolution in days)
    """
    # Try TemporalExtents first
    temporal_extents = umm_metadata.get("TemporalExtents", [])
    for extent in temporal_extents:
        temp_res = extent.get("TemporalResolution")
        if temp_res:
            unit = temp_res.get("Unit", "")
            value = temp_res.get("Value")

            # Handle "Constant" or "Varies" units (no numeric value)
            if unit in ("Constant", "Varies"):
                return unit, None

            if value is not None:
                resolution_str = f"{value} {unit}"
                resolution_days = _normalize_temporal_to_days(value, unit)
                return resolution_str, resolution_days

    # Fallback: extract from title
    title = umm_metadata.get("EntryTitle", "")
    resolution_str = _extract_temporal_from_title(title)
    if resolution_str:
        resolution_days = _normalize_temporal_from_text(resolution_str)
        return resolution_str, resolution_days

    return None, None


def parse_spatial_resolution(umm_metadata: dict[str, Any]) -> tuple[str | None, float | None]:
    """
    Extract spatial resolution from UMM-C metadata.

    Checks multiple locations in the metadata:
    1. SpatialExtent.HorizontalSpatialDomain.ResolutionAndCoordinateSystem.HorizontalDataResolution
    2. Title (common pattern: "1km", "250m", "0.25 degree")

    Args:
        umm_metadata: UMM-C collection metadata

    Returns:
        Tuple of (human-readable resolution string, resolution in meters)
    """
    spatial_extent = umm_metadata.get("SpatialExtent", {})
    horiz_domain = spatial_extent.get("HorizontalSpatialDomain", {})
    res_system = horiz_domain.get("ResolutionAndCoordinateSystem", {})
    horiz_res = res_system.get("HorizontalDataResolution", {})

    # Check for "Varies" or "Point" resolution
    if horiz_res.get("VariesResolution"):
        return "Varies", None
    if horiz_res.get("PointResolution"):
        return "Point", None

    # Check GriddedResolutions
    for gridded in horiz_res.get("GriddedResolutions", []):
        x_dim = gridded.get("XDimension")
        unit = gridded.get("Unit", "")
        if x_dim is not None:
            resolution_str = f"{x_dim} {unit}"
            resolution_meters = _normalize_spatial_to_meters(x_dim, unit)
            return resolution_str, resolution_meters

    # Check NonGriddedResolutions
    for non_gridded in horiz_res.get("NonGriddedResolutions", []):
        x_dim = non_gridded.get("XDimension")
        unit = non_gridded.get("Unit", "")
        if x_dim is not None:
            resolution_str = f"{x_dim} {unit}"
            resolution_meters = _normalize_spatial_to_meters(x_dim, unit)
            return resolution_str, resolution_meters

    # Fallback: extract from title
    title = umm_metadata.get("EntryTitle", "")
    resolution_str = _extract_spatial_from_title(title)
    if resolution_str:
        resolution_meters = _normalize_spatial_from_text(resolution_str)
        return resolution_str, resolution_meters

    return None, None


def parse_temporal_coverage(umm_metadata: dict[str, Any]) -> TemporalCoverage:
    """
    Extract temporal coverage (start/end dates) from UMM-C metadata.

    Args:
        umm_metadata: UMM-C collection metadata

    Returns:
        TemporalCoverage with start/end dates and ongoing flag
    """
    temporal_extents = umm_metadata.get("TemporalExtents", [])

    start_date = None
    end_date = None
    is_ongoing = False

    for extent in temporal_extents:
        # Check EndsAtPresentFlag
        if extent.get("EndsAtPresentFlag"):
            is_ongoing = True

        for range_dt in extent.get("RangeDateTimes", []):
            begin = range_dt.get("BeginningDateTime")
            end = range_dt.get("EndingDateTime")

            if begin:
                try:
                    parsed = datetime.fromisoformat(begin.replace("Z", "+00:00"))
                    if start_date is None or parsed < start_date:
                        start_date = parsed
                except ValueError:
                    pass

            if end:
                try:
                    parsed = datetime.fromisoformat(end.replace("Z", "+00:00"))
                    if end_date is None or parsed > end_date:
                        end_date = parsed
                except ValueError:
                    pass

    return TemporalCoverage(
        start_date=start_date,
        end_date=end_date,
        is_ongoing=is_ongoing or end_date is None,
    )


def parse_resolution_info(umm_metadata: dict[str, Any]) -> ResolutionInfo:
    """
    Parse all resolution information from UMM-C metadata.

    Args:
        umm_metadata: UMM-C collection metadata

    Returns:
        ResolutionInfo with temporal and spatial resolution details
    """
    temp_str, temp_days = parse_temporal_resolution(umm_metadata)
    spat_str, spat_meters = parse_spatial_resolution(umm_metadata)

    return ResolutionInfo(
        temporal_resolution=temp_str,
        temporal_resolution_value=temp_days,
        spatial_resolution=spat_str,
        spatial_resolution_value=spat_meters,
    )


def extract_platforms(umm_metadata: dict[str, Any]) -> list[str]:
    """
    Extract platform names from UMM-C metadata.

    Args:
        umm_metadata: UMM-C collection metadata

    Returns:
        List of platform short names
    """
    platforms = []
    for platform in umm_metadata.get("Platforms", []):
        short_name = platform.get("ShortName")
        if short_name:
            platforms.append(short_name)
    return platforms


def extract_instruments(umm_metadata: dict[str, Any]) -> list[str]:
    """
    Extract instrument names from UMM-C metadata.

    Args:
        umm_metadata: UMM-C collection metadata

    Returns:
        List of instrument short names
    """
    instruments = []
    for platform in umm_metadata.get("Platforms", []):
        for instrument in platform.get("Instruments", []):
            short_name = instrument.get("ShortName")
            if short_name and short_name not in instruments:
                instruments.append(short_name)
    return instruments


# --- Private helper functions ---


def _normalize_temporal_to_days(value: float, unit: str) -> float | None:
    """Convert temporal resolution to days for comparison."""
    unit_lower = unit.lower()

    multipliers = {
        "second": 1 / 86400,
        "minute": 1 / 1440,
        "hour": 1 / 24,
        "day": 1,
        "week": 7,
        "month": 30,
        "year": 365,
        "diurnal": 1,
    }

    for key, mult in multipliers.items():
        if key in unit_lower:
            return value * mult

    return None


def _extract_temporal_from_title(title: str) -> str | None:
    """Extract temporal resolution from collection title using patterns."""
    patterns = [
        r"\b(daily)\b",
        r"\b(monthly)\b",
        r"\b(weekly)\b",
        r"\b(yearly|annual)\b",
        r"\b(hourly)\b",
        r"\b(\d+)[-\s]?(day|hour|month|year|minute)s?\b",
        r"\b(\d+)[-\s]?(day)\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, title, re.IGNORECASE)
        if match:
            return match.group(0).strip()

    return None


def _normalize_temporal_from_text(text: str) -> float | None:
    """Convert text-based temporal resolution to days."""
    text_lower = text.lower()

    # Simple mappings
    simple = {
        "daily": 1,
        "hourly": 1 / 24,
        "weekly": 7,
        "monthly": 30,
        "yearly": 365,
        "annual": 365,
    }

    for key, days in simple.items():
        if key in text_lower:
            return days

    # Try to parse "N-day" patterns
    match = re.search(r"(\d+)[-\s]?day", text_lower)
    if match:
        return float(match.group(1))

    return None


def _extract_spatial_from_title(title: str) -> str | None:
    """Extract spatial resolution from collection title using patterns."""
    patterns = [
        r"\b(\d+(?:\.\d+)?)\s*(m|km|meter|kilometer)s?\b",
        r"\b(\d+(?:\.\d+)?)\s*(deg|degree)s?\b",
        r"\b(\d+(?:\.\d+)?)\s*(arc[-\s]?sec|arcsec)s?\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, title, re.IGNORECASE)
        if match:
            return match.group(0).strip()

    return None


def _normalize_spatial_to_meters(value: float, unit: str) -> float | None:  # pylint: disable=too-many-return-statements
    """Convert spatial resolution to meters for comparison."""
    unit_lower = unit.lower()

    if unit_lower in ("m", "meter", "meters"):
        return value
    if unit_lower in ("km", "kilometer", "kilometers"):
        return value * 1000
    if "degree" in unit_lower or "deg" in unit_lower:
        # Approximate: 1 degree ~ 111km at equator
        return value * 111000
    if "arc" in unit_lower and "sec" in unit_lower:
        # Arc-second: ~30m at equator
        return value * 30
    if "nautical" in unit_lower:
        return value * 1852
    if "statute" in unit_lower or "mile" in unit_lower:
        return value * 1609

    return None


def _normalize_spatial_from_text(text: str) -> float | None:
    """Convert text-based spatial resolution to meters."""
    # Try to parse "Nm" or "Nkm" patterns
    match = re.search(r"(\d+(?:\.\d+)?)\s*(m|km|meter|kilometer)", text, re.IGNORECASE)
    if match:
        value = float(match.group(1))
        unit = match.group(2)
        return _normalize_spatial_to_meters(value, unit)

    # Try degree patterns
    match = re.search(r"(\d+(?:\.\d+)?)\s*deg", text, re.IGNORECASE)
    if match:
        value = float(match.group(1))
        return value * 111000

    return None
