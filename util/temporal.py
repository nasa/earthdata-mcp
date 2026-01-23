"""
Temporal utilities for extracting and comparing temporal metadata.

This module provides functions to:
- Extract temporal extent (start/end dates, ongoing flag)
- Extract temporal resolution from UMM-C metadata
- Normalize resolutions for comparison
- Detect disambiguation scenarios between collections
"""

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from util.resolution import check_disambiguation, group_by_resolution


@dataclass
class TemporalResolution:
    """Normalized temporal resolution for comparison."""

    value: float
    unit: str
    hours: float  # Normalized to hours for comparison

    def __str__(self) -> str:
        """Human-readable format."""
        if self.value == 1:
            return self.unit
        return f"{int(self.value) if self.value == int(self.value) else self.value}-{self.unit}"


# Conversion factors to hours
UNIT_TO_HOURS: dict[str, float] = {
    "Second": 1 / 3600,
    "Minute": 1 / 60,
    "Hour": 1,
    "Day": 24,
    "Week": 24 * 7,
    "Month": 24 * 30,  # Approximate
    "Year": 24 * 365,  # Approximate
}

# Patterns for parsing temporal resolution from collection titles
# Order matters: specific patterns (N-day, N-hour) before generic (daily, hourly)
# Each tuple is (regex_pattern, default_value, unit)
# - default_value=None means extract the value from the regex capture group
# - default_value=1 means use 1 as the value (for patterns like "daily", "hourly")
#
# Note: For hourly, we use negative lookbehind (?<!-) to avoid matching
# version numbers like "MERRA-2 Hourly" as 2 Hour
TEMPORAL_TITLE_PATTERNS: list[tuple[str, int | None, str]] = [
    # Specific patterns with numbers first
    (r"\b(\d+)[-\s]?day\b", None, "Day"),
    (r"(?<!-)(\d+)[-\s]+hour(?:ly)?\b", None, "Hour"),  # handles "12 hourly" and "12-hourly"
    (r"\b(\d+)[-\s]?month\b", None, "Month"),
    (r"\b(\d+)[-\s]?minute\b", None, "Minute"),
    (r"\b(\d+)[-\s]?week\b", None, "Week"),
    (r"\b(\d+)[-\s]?year\b", None, "Year"),
    # Generic patterns second
    (r"\bdaily\b", 1, "Day"),
    (r"\bhourly\b", 1, "Hour"),
    (r"\bmonthly\b", 1, "Month"),
    (r"\bweekly\b", 1, "Week"),
    (r"\bannual\b", 1, "Year"),
]


def parse_iso_datetime(date_str: str) -> datetime | None:
    """Parse ISO datetime string, returning None on failure."""
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except ValueError:
        return None


def extract_temporal_extent(
    metadata: dict[str, Any],
) -> tuple[datetime | None, datetime | None, bool]:
    """
    Extract temporal start, end, and ongoing flag from UMM-C metadata.

    Args:
        metadata: UMM-C metadata dict (can be raw or enriched)

    Returns:
        Tuple of (start_date, end_date, is_ongoing)
    """
    start_date = None
    end_date = None
    is_ongoing = False

    temporal_extents = metadata.get("TemporalExtents", [])
    if not temporal_extents:
        return None, None, False

    for extent in temporal_extents:
        if extent.get("EndsAtPresentFlag"):
            is_ongoing = True

        # Handle SingleDateTimes
        for date_str in extent.get("SingleDateTimes", []):
            parsed = parse_iso_datetime(date_str)
            if parsed:
                if start_date is None or parsed < start_date:
                    start_date = parsed
                if end_date is None or parsed > end_date:
                    end_date = parsed

        # Handle RangeDateTimes
        for range_dt in extent.get("RangeDateTimes", []):
            begin = parse_iso_datetime(range_dt.get("BeginningDateTime", ""))
            end = parse_iso_datetime(range_dt.get("EndingDateTime", ""))

            if begin and (start_date is None or begin < start_date):
                start_date = begin
            if end and (end_date is None or end > end_date):
                end_date = end

    # If no end date, consider ongoing
    if end_date is None:
        is_ongoing = True

    return start_date, end_date, is_ongoing


def extract_temporal_resolution(metadata: dict[str, Any]) -> TemporalResolution | None:
    """
    Extract temporal resolution from UMM-C metadata.

    Reads from TemporalExtents[].TemporalResolution field.
    Does NOT parse from title - use enriched_metadata if you want title-derived values.

    Args:
        metadata: UMM-C metadata dict (typically enriched_metadata for full coverage)

    Returns:
        TemporalResolution if found, None otherwise
    """
    temporal_extents = metadata.get("TemporalExtents", [])

    for extent in temporal_extents:
        resolution = extent.get("TemporalResolution")
        if not resolution:
            continue

        unit = resolution.get("Unit")
        if not unit:
            continue

        # Handle "Varies" or "Constant" special values
        if unit in ("Varies", "Constant"):
            return TemporalResolution(value=0, unit=unit, hours=0)

        value = resolution.get("Value", 1)
        hours = value * UNIT_TO_HOURS.get(unit, 0)

        return TemporalResolution(value=value, unit=unit, hours=hours)

    return None


def parse_temporal_resolution_from_title(title: str) -> dict[str, Any] | None:
    """
    Parse temporal resolution from collection title.

    Returns UMM-C compliant TemporalResolution object.
    This is used by the enrichment process, not at query time.

    See TEMPORAL_TITLE_PATTERNS for the list of patterns used.
    """
    title_lower = title.lower()

    for pattern, default_value, unit in TEMPORAL_TITLE_PATTERNS:
        match = re.search(pattern, title_lower)
        if match:
            value = default_value if default_value is not None else int(match.group(1))
            return {"Value": value, "Unit": unit}

    return None


def group_by_temporal_resolution(
    collections: list[dict[str, Any]],
) -> dict[str | None, list[dict[str, Any]]]:
    """
    Group collections by their temporal resolution.

    Args:
        collections: List of collection metadata dicts

    Returns:
        Dict mapping resolution string (e.g., "Daily", "8-Day") to collections
    """
    return group_by_resolution(collections, extract_temporal_resolution)


def check_temporal_disambiguation(
    collections: list[dict[str, Any]],
) -> tuple[bool, list[str]]:
    """
    Check if collections need disambiguation based on temporal resolution.

    Args:
        collections: List of collection metadata dicts (should be enriched_metadata)

    Returns:
        Tuple of (needs_disambiguation, list of distinct resolutions found)
    """
    return check_disambiguation(
        collections,
        extract_temporal_resolution,
        exclude_units=("Varies", "Constant"),
        sort_key_fn=_resolution_sort_key,
    )


def _resolution_sort_key(resolution_str: str) -> float:
    """Sort resolutions by duration (shortest first)."""
    # Parse the resolution string back to get hours
    # Format is either "Unit" (e.g., "Day") or "N-Unit" (e.g., "8-Day")
    parts = resolution_str.split("-")
    if len(parts) == 2:
        value = float(parts[0])
        unit = parts[1]
    else:
        value = 1
        unit = parts[0]

    return value * UNIT_TO_HOURS.get(unit, 0)
