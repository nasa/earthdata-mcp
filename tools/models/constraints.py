"""
Constraint models for spatial and temporal query filtering.

Defines models that represent extracted or user-provided constraints that filter
discovery results to specific geographic areas and time periods.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class SpatialInput(BaseModel):
    """User-provided spatial constraint via explicit geometry or bounding box.

    Use this to provide a spatial filter directly without relying on natural language
    geocoding. Supports WKT geometry, GeoJSON Feature, or bounding box.
    """

    wkt: str | None = Field(
        None,
        description=(
            "WKT (Well-Known Text) representation of the spatial area. "
            "Examples: 'POINT(-87.5 30)', 'POLYGON((-87 30, -87 31, -86 31, -86 30, -87 30))'"
        ),
    )
    geojson_feature: dict | None = Field(
        None,
        description=(
            "GeoJSON Feature with geometry. Single Feature only (not FeatureCollection). "
            'Example: {"type": "Feature", "geometry": {"type": "Point", "coordinates": [-87.5, 30]}}'
        ),
    )
    bbox: dict | None = Field(
        None,
        description=(
            'Bounding box as {"west": -87.5, "south": 29, "east": -86, "north": 31}. '
            "Coordinates in WGS84 (EPSG:4326)."
        ),
    )


class TemporalConstraint(BaseModel):
    """Extracted or user-provided temporal constraint."""

    start_date: datetime | None = Field(None, description="Start of temporal range (inclusive)")
    end_date: datetime | None = Field(None, description="End of temporal range (inclusive)")
    reasoning: str | None = Field(
        None, description="Explanation of how the constraint was extracted"
    )


class SpatialConstraint(BaseModel):
    """Extracted or user-provided spatial constraint."""

    location: str | None = Field(None, description="Original location text from user query")
    wkt_geometry: str | None = Field(None, description="WKT representation of the spatial area")
    reasoning: str | None = Field(
        None, description="Explanation of how the constraint was extracted"
    )
