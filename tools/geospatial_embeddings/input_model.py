"""Input model for geospatial/location queries."""

from pydantic import BaseModel, Field


class LocationInput(BaseModel):
    """
    Input model for location queries.

    Validates natural language strings describing locations.
    """

    location: str = Field(
        ...,
        description="A natural language location query (e.g., 'San Francisco Bay Area')",
    )
