"""
Output model for geospatial/location queries.

Defines the structure of geocoding results from natural language location queries.
"""

from pydantic import BaseModel, Field
from typing import Optional


class GeospatialOutput(BaseModel):
    """
    Output model for geocoding responses.

    Can represent both successful and failed geocoding attempts.
    - For success: geoLocation and geometry are populated, success=True
    - For errors: error is populated, success=False
    """

    success: bool = Field(
        ...,
        description="Whether the geocoding was successful",
    )

    # Success fields (populated when success=True)
    geoLocation: Optional[str] = Field(
        None,
        description="The original location query string (only present on success)",
        examples=["San Francisco Bay Area"],
    )
    geometry: Optional[str] = Field(
        None,
        description="WKT (Well-Known Text) representation of the geometry (only present on success)",
        examples=[
            "POLYGON((-122.5 37.7, -122.3 37.7, -122.3 37.8, -122.5 37.8, -122.5 37.7))",
            "POINT(-122.4194 37.7749)",
        ],
    )

    # Error field (populated when success=False)
    error: Optional[str] = Field(
        None,
        description="Error message describing why geocoding failed (only present on error)",
        examples=[
            "Unable to geocode the location 'NonexistentPlace123'.",
            "No location query provided. Please specify a location.",
        ],
    )

    from_cache: bool = Field(
        default=False,
        description="Whether the result was retrieved from cache",
    )

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "examples": [
                {
                    "success": True,
                    "geoLocation": "San Francisco Bay Area",
                    "geometry": "POLYGON((-122.5 37.7, -122.3 37.7, -122.3 37.8, -122.5 37.8, -122.5 37.7))",
                    "from_cache": False,
                },
                {
                    "success": True,
                    "geoLocation": "San Francisco",
                    "geometry": "POINT(-122.4194 37.7749)",
                    "from_cache": True,
                },
                {
                    "success": False,
                    "error": "Unable to geocode the location 'NonexistentPlace123'.",
                    "from_cache": False,
                },
                {
                    "success": False,
                    "error": "No location query provided. Please specify a location.",
                    "from_cache": False,
                },
            ]
        }
