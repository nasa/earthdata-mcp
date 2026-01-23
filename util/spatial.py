"""
Spatial utilities for extracting and comparing spatial metadata.

This module provides functions to:
- Extract spatial extent (WKT geometry, global flag)
- Extract spatial resolution from UMM-C metadata
- Normalize resolutions for comparison
- Detect disambiguation scenarios between collections
"""

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class SpatialResolution:
    """Normalized spatial resolution for comparison."""

    x_dimension: float
    y_dimension: float
    unit: str
    meters: float  # Normalized to meters for comparison

    def __str__(self) -> str:
        """Human-readable format."""
        # Use X dimension for display (assume square pixels)
        value = self.x_dimension
        if value == int(value):
            value = int(value)

        # Abbreviate units for display
        unit_abbrev = {
            "Kilometers": "km",
            "Meters": "m",
            "Decimal Degrees": "deg",
            "Statute Miles": "mi",
            "Nautical Miles": "nmi",
        }
        return f"{value} {unit_abbrev.get(self.unit, self.unit)}"


# Conversion factors to meters
UNIT_TO_METERS: dict[str, float] = {
    "Meters": 1,
    "Kilometers": 1000,
    "Decimal Degrees": 111_320,  # Approximate meters per degree at equator
    "Statute Miles": 1609.34,
    "Nautical Miles": 1852,
}

# Patterns for parsing spatial resolution from collection titles
# Each tuple is (regex_pattern, unit)
SPATIAL_TITLE_PATTERNS: list[tuple[str, str]] = [
    (r"\b(\d+(?:\.\d+)?)\s*km\b", "Kilometers"),
    (r"\b(\d+(?:\.\d+)?)\s*m\b", "Meters"),
    (r"\b(\d+(?:\.\d+)?)\s*(?:deg|degree)s?\b", "Decimal Degrees"),
]


def extract_spatial_extent(metadata: dict[str, Any]) -> tuple[str | None, bool]:
    """
    Extract spatial extent as WKT and determine if global.

    Prefers GPolygons over BoundingRectangles. Returns None for Points/Lines.

    Args:
        metadata: UMM-C metadata

    Returns:
        Tuple of (wkt_geometry, is_global)
    """
    spatial = metadata.get("SpatialExtent", {})
    horiz = spatial.get("HorizontalSpatialDomain", {})
    geometry = horiz.get("Geometry", {})

    coordinates = None
    is_global = False

    # Try GPolygons first
    gpolygons = geometry.get("GPolygons", [])
    if gpolygons:
        gpolygon = gpolygons[0]
        points = gpolygon.get("Boundary", {}).get("Points", [])
        if points:
            coordinates = [(p["Longitude"], p["Latitude"]) for p in points]

    # Fall back to BoundingRectangles
    if coordinates is None:
        bboxes = geometry.get("BoundingRectangles", [])
        if bboxes:
            rect = bboxes[0]
            west = rect.get("WestBoundingCoordinate")
            east = rect.get("EastBoundingCoordinate")
            north = rect.get("NorthBoundingCoordinate")
            south = rect.get("SouthBoundingCoordinate")

            if all(coord is not None for coord in [west, east, north, south]):
                coordinates = [
                    (west, north),
                    (east, north),
                    (east, south),
                    (west, south),
                    (west, north),  # Close the polygon
                ]

                # Check if global
                lon_span = east - west
                lat_span = north - south
                is_global = lon_span >= 350 and lat_span >= 170

    if not coordinates:
        return None, False

    # Convert to WKT
    wkt = f"POLYGON(({', '.join(f'{lon} {lat}' for lon, lat in coordinates)}))"

    return wkt, is_global


def extract_spatial_resolution(metadata: dict[str, Any]) -> SpatialResolution | None:
    """
    Extract spatial resolution from UMM-C metadata.

    Reads from SpatialExtent.HorizontalSpatialDomain.ResolutionAndCoordinateSystem.
    Does NOT parse from title - use enriched_metadata if you want title-derived values.

    Args:
        metadata: UMM-C metadata dict (typically enriched_metadata for full coverage)

    Returns:
        SpatialResolution if found, None otherwise
    """
    spatial = metadata.get("SpatialExtent", {})
    horiz = spatial.get("HorizontalSpatialDomain", {})
    res_sys = horiz.get("ResolutionAndCoordinateSystem", {})
    horiz_res = res_sys.get("HorizontalDataResolution", {})

    # Handle special values
    if horiz_res.get("VariesResolution"):
        return SpatialResolution(x_dimension=0, y_dimension=0, unit="Varies", meters=0)

    if horiz_res.get("PointResolution"):
        return SpatialResolution(x_dimension=0, y_dimension=0, unit="Point", meters=0)

    # Try GriddedResolutions first
    gridded = horiz_res.get("GriddedResolutions", [])
    if gridded:
        res = gridded[0]
        x_dim = res.get("XDimension", 0)
        y_dim = res.get("YDimension", x_dim)
        unit = res.get("Unit", "")

        if unit and x_dim:
            meters = x_dim * UNIT_TO_METERS.get(unit, 0)
            return SpatialResolution(x_dimension=x_dim, y_dimension=y_dim, unit=unit, meters=meters)

    # Try NonGriddedResolutions
    non_gridded = horiz_res.get("NonGriddedResolutions", [])
    if non_gridded:
        res = non_gridded[0]
        x_dim = res.get("XDimension", 0)
        y_dim = res.get("YDimension", x_dim)
        unit = res.get("Unit", "")

        if unit and x_dim:
            meters = x_dim * UNIT_TO_METERS.get(unit, 0)
            return SpatialResolution(x_dimension=x_dim, y_dimension=y_dim, unit=unit, meters=meters)

    return None


def parse_spatial_resolution_from_title(title: str) -> dict[str, Any] | None:
    """
    Parse spatial resolution from collection title.

    Returns UMM-C compliant GriddedResolution object.
    This is used by the enrichment process, not at query time.
    """
    for pattern, unit in SPATIAL_TITLE_PATTERNS:
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


def group_by_spatial_resolution(
    collections: list[dict[str, Any]],
) -> dict[str | None, list[dict[str, Any]]]:
    """
    Group collections by their spatial resolution.

    Args:
        collections: List of collection metadata dicts

    Returns:
        Dict mapping resolution string (e.g., "1 km", "250 m") to collections
    """
    groups: dict[str | None, list[dict[str, Any]]] = {}

    for collection in collections:
        resolution = extract_spatial_resolution(collection)
        key = str(resolution) if resolution else None
        groups.setdefault(key, []).append(collection)

    return groups


def check_spatial_disambiguation(
    collections: list[dict[str, Any]],
) -> tuple[bool, list[str]]:
    """
    Check if collections need disambiguation based on spatial resolution.

    Args:
        collections: List of collection metadata dicts (should be enriched_metadata)

    Returns:
        Tuple of (needs_disambiguation, list of distinct resolutions found)
    """
    resolutions: set[str] = set()

    for collection in collections:
        resolution = extract_spatial_resolution(collection)
        if resolution and resolution.unit not in ("Varies", "Point"):
            resolutions.add(str(resolution))

    # Need disambiguation if more than one distinct resolution
    needs_disambiguation = len(resolutions) > 1
    return needs_disambiguation, sorted(resolutions, key=_spatial_resolution_sort_key)


def _spatial_resolution_sort_key(resolution_str: str) -> float:
    """Sort resolutions by size (smallest/finest first)."""
    # Parse the resolution string back to get meters
    # Format is "N unit" (e.g., "1 km", "250 m", "0.25 deg")
    parts = resolution_str.split()
    if len(parts) != 2:
        return float("inf")

    try:
        value = float(parts[0])
    except ValueError:
        return float("inf")

    unit_abbrev_to_full = {
        "km": "Kilometers",
        "m": "Meters",
        "deg": "Decimal Degrees",
        "mi": "Statute Miles",
        "nmi": "Nautical Miles",
    }

    unit = unit_abbrev_to_full.get(parts[1], parts[1])
    return value * UNIT_TO_METERS.get(unit, 0)
