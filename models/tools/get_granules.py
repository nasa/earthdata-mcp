"""Input and output models for the get_granules MCP tool."""

from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field

from models.pagination import CursorParam, FieldsParam, LimitParam
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
            "POINT(lon lat), or LINESTRING(lon lat, ...)."
            "Finds granules with spatial extent intersecting this area. "
            "CMR returns any granule that touches this shape, so precise geometries are "
            "preferred to prevent false positives. Set this whenever the user specifies a geographic region "
            "— omitting it returns granules from the entire globe regardless of location."
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

DayNightFlagParam = Annotated[
    str | None,
    Field(
        description=(
            "Filter granules by day/night acquisition flag. Values: 'DAY', 'NIGHT', 'UNSPECIFIED'."
        )
    ),
]

SortKeyParam = Annotated[
    str | None,
    Field(
        description=(
            "Sort key for granule results. "
            "e.g., '-start_date' (newest first), 'start_date' (oldest first). "
            "CMR default is relevance score. "
            "For ongoing or near-real-time (NRT) missions where the user wants the most recent data, "
            "always use '-start_date' — CMR's default relevance scoring may return historical data first "
            "if sort_key is not explicitly set."
        )
    ),
]


class GranuleResult(BaseModel):
    """Minimal granule result for direct CMR-backed retrieval."""

    access_urls: list[str] = Field(
        default_factory=list,
        description="Actionable data access URLs (Note: Access requires Earthdata Login authentication)",
    )
    additional_attributes: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Provider-specific attributes (e.g., tile coords, quality flags) — array of {name, values[]}",
    )
    bounding_box: list[float] | None = Field(
        None,
        description="[West, South, East, North] Minimum Bounding Rectangle (MBR). Note: For swath data or irregular polygons, this bounding box fully encloses the data but may contain empty space at the corners.",
    )
    cloud_cover: float | None = Field(None, description="Cloud cover percentage")
    collection_concept_id: str | None = Field(None, description="Parent collection concept ID")
    concept_id: str = Field(..., description="CMR granule concept ID")
    data_format: str | None = Field(None, description="File format (e.g., NetCDF-4, GeoTIFF)")
    day_night_flag: str | None = Field(None, description="DAY, NIGHT, BOTH, or UNSPECIFIED")
    granule_ur: str = Field(..., description="Granule UR")
    native_id: str | None = Field(None, description="The native ID of the granule record")
    orbit_info: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Orbit calculated spatial domains — array of {orbit_number, equator_crossing_longitude, equator_crossing_date_time}",
    )
    producer_granule_id: str | None = Field(None, description="Producer granule ID")
    production_date: datetime | None = Field(
        None, description="Date the granule was generated (ProductionDateTime)"
    )
    provider_id: str | None = Field(None, description="The provider ID of the granule")
    revision_id: int | None = Field(None, description="The revision ID of the granule metadata")
    size_mb: float | None = Field(None, description="Size of the data granule in MB")
    time_end: datetime | None = Field(None, description="Granule temporal end")
    time_start: datetime | None = Field(None, description="Granule temporal start")


class GetGranulesInput(BaseModel):
    """Input model for get_granules."""

    model_config = ConfigDict(extra="forbid")

    collection_concept_id: CollectionConceptIdParam
    temporal_start_date: TemporalStartDateParam = None
    temporal_end_date: TemporalEndDateParam = None
    spatial_wkt_geometry: SpatialWktGeometryParam = None
    cloud_cover_min: CloudCoverMinParam = None
    cloud_cover_max: CloudCoverMaxParam = None
    day_night_flag: DayNightFlagParam = None
    sort_key: SortKeyParam = None
    limit: LimitParam = 10
    cursor: CursorParam = None
    fields: FieldsParam


class GetGranulesOutput(BaseCmrSearchOutput):
    """Output model for get_granules."""

    granules: list[GranuleResult] = Field(
        default_factory=list, description="Normalized granule results mapped from UMM-G"
    )
    next_cursor: str | None = Field(
        default=None, description="Pagination token for the next page of results"
    )
