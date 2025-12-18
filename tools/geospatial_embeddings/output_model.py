"""
Output model for geospatial/location queries.

Defines the structure of geocoding results from natural language location queries.
"""

from pydantic import BaseModel, Field
from typing import Optional, Union, Literal, List, Any


class PointGeometry(BaseModel):
    """GeoJSON Point geometry."""

    type: Literal["Point"] = Field(default="Point")
    coordinates: List[float] = Field(
        ...,
        description="[longitude, latitude]",
        min_length=2,
        max_length=2,
        examples=[[-122.4194, 37.7749]],
    )


class PolygonGeometry(BaseModel):
    """GeoJSON Polygon geometry."""

    type: Literal["Polygon"] = Field(default="Polygon")
    coordinates: List[List[List[float]]] = Field(
        ...,
        description="Array of linear rings (first is exterior, rest are holes)",
        examples=[
            [
                [
                    [-122.5, 37.7],
                    [-122.3, 37.7],
                    [-122.3, 37.8],
                    [-122.5, 37.8],
                    [-122.5, 37.7],
                ]
            ]
        ],
    )


class MultiPolygonGeometry(BaseModel):
    """GeoJSON MultiPolygon geometry."""

    type: Literal["MultiPolygon"] = Field(default="MultiPolygon")
    coordinates: List[List[List[List[float]]]] = Field(
        ...,
        description="Array of Polygon coordinate arrays",
    )


class BoundingBox(BaseModel):
    """Bounding box representation."""

    bbox: List[float] = Field(
        ...,
        description="[min_lon, min_lat, max_lon, max_lat]",
        min_length=4,
        max_length=4,
        examples=[[-122.5, 37.7, -122.3, 37.8]],
    )


# Union type for all geometry types
GeometryType = Union[PointGeometry, PolygonGeometry, MultiPolygonGeometry, BoundingBox]


class GeospatialOutput(BaseModel):
    """
    Output model for geospatial location queries.

    Contains the geometry information for a location query, or error information if geocoding failed.
    """

    geometry: Optional[GeometryType] = Field(
        None,
        description="GeoJSON geometry object (Point, Polygon, MultiPolygon, or bounding box)",
    )
    location: Optional[str] = Field(
        None,
        description="The original location query string",
        examples=["San Francisco Bay Area"],
    )
    success: bool = Field(
        default=True,
        description="Whether the geocoding was successful",
    )
    error: Optional[str] = Field(
        None,
        description="Error message if geocoding failed",
    )

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "examples": [
                {
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [-122.5, 37.7],
                                [-122.3, 37.7],
                                [-122.3, 37.8],
                                [-122.5, 37.8],
                                [-122.5, 37.7],
                            ]
                        ],
                    },
                    "location": "San Francisco Bay Area",
                    "success": True,
                    "error": None,
                },
                {
                    "geometry": {"type": "Point", "coordinates": [-122.4194, 37.7749]},
                    "location": "San Francisco",
                    "success": True,
                    "error": None,
                },
                {
                    "geometry": None,
                    "location": "NonexistentPlace123",
                    "success": False,
                    "error": "Unable to geocode the location 'NonexistentPlace123'.",
                },
            ]
        }
