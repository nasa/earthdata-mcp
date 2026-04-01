"""Input and output models for the get_granules MCP tool."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field

from models.tools.cmr_search import BaseCmrSearchOutput

CollectionConceptIdParam = Annotated[
    str,
    Field(
        description=(
            "Parent collection concept ID (format: C<number>-<PROVIDER>, "
            "e.g., C2723758340-GES_DISC). Required to scope granule search."
        )
    ),
]

TemporalStartDateParam = Annotated[
    str | None,
    Field(
        description=(
            "Start of temporal filter in ISO 8601 format (e.g., 2024-01-01T00:00:00Z). "
            "Finds granules whose temporal extent overlaps this window. "
            "Set this whenever the user specifies a time period — omitting it returns granules "
            "from the entire collection archive regardless of date."
        )
    ),
]

TemporalEndDateParam = Annotated[
    str | None,
    Field(
        description=(
            "End of temporal filter in ISO 8601 format (e.g., 2024-01-31T23:59:59Z). "
            "Finds granules whose temporal extent overlaps this window. "
            "Set this whenever the user specifies a time period — omitting it returns granules "
            "from the entire collection archive regardless of date."
        )
    ),
]

SpatialWktGeometryParam = Annotated[
    str | None,
    Field(
        description=(
            "Spatial filter as WKT geometry. Supported types: POLYGON((lon lat, ...)), "
            "POINT(lon lat), LINESTRING(lon lat, ...), "
            "or ENVELOPE(minLon, maxLon, maxLat, minLat). "
            "Finds granules with spatial extent intersecting this area. "
            "Set this whenever the user specifies a geographic region — omitting it returns "
            "granules from the entire globe regardless of location."
        )
    ),
]


class GranuleResult(BaseModel):
    """Minimal granule result for direct CMR-backed retrieval."""

    concept_id: str = Field(..., description="CMR granule concept ID")
    collection_concept_id: str | None = Field(None, description="Parent collection concept ID")
    granule_ur: str = Field(..., description="Granule UR")
    producer_granule_id: str | None = Field(None, description="Producer granule ID")
    time_start: datetime | None = Field(None, description="Granule temporal start")
    time_end: datetime | None = Field(None, description="Granule temporal end")
    access_urls: list[str] = Field(
        default_factory=list,
        description="Actionable data access URLs (Note: Access requires Earthdata Login authentication)",
    )


class GetGranulesInput(BaseModel):
    """Input model for get_granules."""

    collection_concept_id: CollectionConceptIdParam
    temporal_start_date: TemporalStartDateParam = None
    temporal_end_date: TemporalEndDateParam = None
    spatial_wkt_geometry: SpatialWktGeometryParam = None


class GetGranulesOutput(BaseCmrSearchOutput):
    """Output model for get_granules."""

    granules: list[GranuleResult] = Field(
        default_factory=list, description="Normalized granule results mapped from UMM-G (max 20)"
    )
