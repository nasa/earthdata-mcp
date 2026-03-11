"""Generic geometry helpers used across discover_data link builders."""

import math
import re


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

    # Handle antimeridian-crossing bboxes (east < west) using wrapped span.
    # Example: west=170, east=-170 should span 20 degrees centered on 180/-180.
    if east < west:
        lon_span = east + 360.0 - west
        center_lon = west + lon_span / 2.0
        center_lon = ((center_lon + 180.0) % 360.0) - 180.0
    else:
        lon_span = east - west
        center_lon = (west + east) / 2.0

    lat_span = north - south
    max_span = max(lon_span, lat_span, 0.001)  # guard against zero-area
    zoom = math.log2(360.0 / max_span) + 1.0
    return center_lat, center_lon, zoom
