"""Input and output models for the get_collections MCP tool."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field

from models.tools.cmr_search import SearchStatus

QueryParam = Annotated[
    str | None,
    Field(
        description=(
            "Free-text keyword search. Case insensitive. Each space-separated word is matched "
            "independently; ALL words must appear somewhere in a collection's indexed fields "
            "(title, summary, short name, GCMD science keywords, platform and instrument names, "
            "project names, processing level, archive centers, additional attributes, etc.). "
            "Wildcards supported: * (zero or more chars), ? (any single char). "
            "Use scientific terms: geophysical variable names ('sea surface temperature', "
            "'soil moisture'), instrument names (MODIS, ASCAT, VIIRS, AIRS, Landsat), or "
            "platform names (Terra, Aqua, SMAP, Sentinel-1). "
            "For known product short names use the short_name parameter instead."
        )
    ),
]

ConceptIdParam = Annotated[
    str | None,
    Field(
        description=(
            "Exact CMR concept ID (format: C<number>-<PROVIDER>, "
            "e.g., C2036882064-POCLOUD). Use for direct lookup of a known collection."
        )
    ),
]

ShortNameParam = Annotated[
    str | None,
    Field(
        description=(
            "Collection short name (e.g., MOD11A1, SPL3SMP, MUR-JPL-L4-GLOB-v4.1). "
            "Exact match by default; wildcards * and ? are supported."
        )
    ),
]

ProviderParam = Annotated[
    str | None,
    Field(
        description=(
            "Data provider short name (e.g., PODAAC, NSIDC_ECS, GESDISC, ORNL_DAAC, "
            "LAADS, GES_DISC, GHRC_DAAC, ASDC, LPDAAC_ECS). "
            "Restricts results to collections from that provider."
        )
    ),
]

TemporalStartDateParam = Annotated[
    str | None,
    Field(
        description=(
            "Start of temporal filter in ISO 8601 format (e.g., 2020-01-01T00:00:00Z). "
            "Restricts results to collections whose declared temporal range overlaps this window. "
            "Set this whenever the user specifies a time period — omitting it returns collections "
            "regardless of when their data was collected."
        )
    ),
]

TemporalEndDateParam = Annotated[
    str | None,
    Field(
        description=(
            "End of temporal filter in ISO 8601 format (e.g., 2020-12-31T23:59:59Z). "
            "Restricts results to collections whose declared temporal range overlaps this window. "
            "Set this whenever the user specifies a time period — omitting it returns collections "
            "regardless of when their data was collected."
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
            "Restricts results to collections whose declared extent intersects this area. "
            "Set this whenever the user specifies a geographic region — omitting it returns "
            "collections with global or unspecified coverage."
        )
    ),
]

PageSizeParam = Annotated[
    int | str,
    Field(description="Number of results per page (default: 10, max: 2000)."),
]

SearchAfterParam = Annotated[
    str | None,
    Field(
        description=(
            "Opaque pagination token from the CMR-Search-After header of a previous response. "
            "Pass it back unchanged to retrieve the next page of results."
        )
    ),
]


class CollectionResult(BaseModel):
    """Minimal collection result for direct CMR-backed discovery."""

    concept_id: str = Field(..., description="CMR collection concept ID")
    short_name: str | None = Field(None, description="Collection short name")
    version: str | None = Field(None, description="Collection version")
    title: str = Field(..., description="Collection title")
    summary: str | None = Field(None, description="Collection summary or abstract")
    time_start: datetime | None = Field(None, description="Start of temporal coverage")
    time_end: datetime | None = Field(None, description="End of temporal coverage")
    is_ongoing: bool = Field(default=False, description="Whether the collection is ongoing")
    platforms: list[str] = Field(default_factory=list, description="Platform short names")
    instruments: list[str] = Field(default_factory=list, description="Instrument short names")


class GetCollectionsInput(BaseModel):
    """Input model for get_collections."""

    query: QueryParam = None
    concept_id: ConceptIdParam = None
    short_name: ShortNameParam = None
    provider: ProviderParam = None
    temporal_start_date: TemporalStartDateParam = None
    temporal_end_date: TemporalEndDateParam = None
    spatial_wkt_geometry: SpatialWktGeometryParam = None
    page_size: int = Field(
        default=10, ge=1, le=2000, description="Results per page (default: 10, max: 2000)."
    )
    search_after: SearchAfterParam = None


class GetCollectionsOutput(BaseModel):
    """Output model for get_collections."""

    status: SearchStatus = Field(..., description="Status of the collection search")
    collections: list[CollectionResult] = Field(default_factory=list, description="Collection page")
    total_hits: int = Field(default=0, description="Total number of matching collections")
    page_size: int = Field(default=0, description="Number of collections returned in this page")
    search_after: str | None = Field(None, description="Search-after token for the next page")
    took_ms: int = Field(default=0, description="CMR processing time in milliseconds")
    error_message: str | None = Field(None, description="Error details when status is error")
