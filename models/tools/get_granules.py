"""Input and output models for the get_granules MCP tool."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

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

CloudCoverMinParam = Annotated[
    float | None,
    Field(
        description=(
            "Minimum cloud cover percentage (0–100, inclusive). "
            "Use with cloud_cover_max to filter optical/visible imagery granules by cloud cover. "
            "Only applicable to collections that report cloud cover (e.g., Landsat, MODIS, "
            "etc). Omit for non-optical data (SAR, altimetry, etc.)."
        ),
        ge=0,
        le=100,
    ),
]

CloudCoverMaxParam = Annotated[
    float | None,
    Field(
        description=(
            "Maximum cloud cover percentage (0–100, inclusive). "
            "Use with cloud_cover_min to filter optical/visible imagery granules by cloud cover. "
            "For example, set cloud_cover_max=20 to find mostly clear scenes. "
            "Only applicable to collections that report cloud cover (e.g., Landsat, MODIS, "
            "etc). Omit for non-optical data (SAR, altimetry, etc.)."
        ),
        ge=0,
        le=100,
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

    model_config = ConfigDict(extra="forbid")

    collection_concept_id: CollectionConceptIdParam
    temporal_start_date: TemporalStartDateParam = None
    temporal_end_date: TemporalEndDateParam = None
    spatial_wkt_geometry: SpatialWktGeometryParam = None
    cloud_cover_min: CloudCoverMinParam = None
    cloud_cover_max: CloudCoverMaxParam = None


class GetGranulesOutput(BaseCmrSearchOutput):
    """Output model for get_granules."""

    granules: list[GranuleResult] = Field(
        default_factory=list, description="Normalized granule results mapped from UMM-G (max 20)"
    )
