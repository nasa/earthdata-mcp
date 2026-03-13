"""Shared models for lightweight CMR search tools."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class SearchStatus(str, Enum):
    """Status for direct CMR search tools."""

    SUCCESS = "success"
    NO_RESULTS = "no_results"
    ERROR = "error"


class TemporalFilter(BaseModel):
    """Optional temporal filter for direct CMR searches."""

    start_date: datetime | None = Field(None, description="Start of temporal range (inclusive)")
    end_date: datetime | None = Field(None, description="End of temporal range (inclusive)")


class SpatialFilter(BaseModel):
    """Optional spatial filter for direct CMR searches."""

    wkt_geometry: str | None = Field(None, description="WKT geometry used for spatial search")
