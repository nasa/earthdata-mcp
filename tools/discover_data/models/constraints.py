"""
Constraint models for spatial and temporal query filtering.

Defines models that represent extracted or user-provided constraints that filter
discovery results to specific geographic areas and time periods.
"""

from datetime import datetime

from pydantic import BaseModel, Field


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
