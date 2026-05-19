"""Input and output models for the get_collections MCP tool."""

from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field

from models.pagination import CursorParam, FieldsParam, LimitParam
from models.tools.cmr_search import BaseCmrSearchOutput

KeywordParam = Annotated[
    str | None,
    Field(
        description=(
            "Free-text keyword search. Case insensitive. "
            "IMPORTANT — CMR uses AND logic: each space-separated word is matched independently "
            "and ALL words must appear somewhere in a collection's indexed fields "
            "(title, summary, short name, GCMD science keywords, platform and instrument names, "
            "project names, processing level, archive centers, additional attributes, etc.). "
            "Words do NOT need to appear in the same field or as a contiguous phrase. "
            "Because every word must match, adding more words makes the search STRICTER, not broader — "
            "the opposite of typical web search engines. Prefer 2–4 precise terms over long queries. "
            "Example: 'soil moisture' (2 terms, broad) vs 'soil moisture SMAP L3' (4 terms, narrow). "
            "Phrase search: wrap the entire value in escaped double quotes to require an exact phrase "
            "(e.g., '\\\"sea surface temperature\\\"'). Only a single phrase is supported; "
            "you cannot mix a phrase with additional standalone words. "
            "Wildcards supported: * (zero or more chars), ? (any single char). "
            "Use scientific terms: geophysical variable names ('sea surface temperature', "
            "'soil moisture'), instrument names (MODIS, ASCAT, VIIRS, AIRS, Landsat, etc.), or "
            "platform names (Terra, Aqua, SMAP, Sentinel-1, etc.). "
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
            "Data provider short name (e.g., PODAAC, NSIDC_ECS, GES_DISC, ORNL_DAAC, "
            "LAADS, GHRC_DAAC, ASDC). "
            "Restricts results to collections from that provider. "
            "WARNING: NASA DAACs are actively migrating assets to the cloud under new provider IDs "
            "(e.g., LPDAAC_ECS → LPCLOUD, PODAAC → POCLOUD). "
            "If you know the exact short_name of a product, do NOT include the provider parameter — "
            "a stale provider ID will silently return 0 results. "
            "Use provider only when the user explicitly filters by archive center."
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
            "POINT(lon lat), or LINESTRING(lon lat, ...)."
            "Restricts results to collections whose declared extent intersects this area. "
            "CMR returns any collection that touches this shape, so precise geometries are "
            "preferred to prevent false positives. Set this whenever the user specifies a geographic region "
            "— omitting it returns collections with global or unspecified coverage."
        )
    ),
]


PlatformParam = Annotated[
    list[str],
    Field(
        default_factory=list,
        description=(
            "Platform short names to filter by (e.g., ['Terra', 'Aqua']). "
            "Most common scientific filter after temporal/spatial."
        ),
    ),
]

InstrumentParam = Annotated[
    list[str],
    Field(
        default_factory=list,
        description=(
            "Instrument short names to filter by (e.g., ['MODIS', 'VIIRS']). "
            "More precise than keyword for instrument filtering."
        ),
    ),
]

ProcessingLevelIdParam = Annotated[
    list[str],
    Field(
        default_factory=list,
        description=(
            "Processing level IDs to filter by (e.g., ['3', '3A']). "
            "Essential for choosing between L2 swath and L3 gridded products."
        ),
    ),
]

HasGranulesParam = Annotated[
    bool | None,
    Field(
        description=(
            "When True, filters to collections that have actual granule data. "
            "Prevents returning metadata-only shells."
        )
    ),
]


class CollectionResult(BaseModel):
    """Minimal collection result for direct CMR-backed discovery."""

    abstract: str | None = Field(None, description="Collection summary or abstract")
    archive_and_distribution_information: list[dict[str, Any]] = Field(
        default_factory=list,
        description="File formats and media types (e.g., [{format, media_type}])",
    )
    bounding_box: list[float] | None = Field(
        None, description="[West, South, East, North] Minimum Bounding Rectangle"
    )
    collection_data_type: str | None = Field(
        None, description="e.g., SCIENCE_QUALITY, NEAR_REAL_TIME"
    )
    collection_progress: str | None = Field(
        None, description="ACTIVE, COMPLETE, DEPRECATED, or PLANNED"
    )
    concept_id: str = Field(..., description="CMR collection concept ID")
    data_centers: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Archiving DAACs — array of {role, short_name}",
    )
    doi: str | None = Field(None, description="Digital Object Identifier")
    entry_title: str = Field(..., description="Collection title")
    instruments: list[str] = Field(default_factory=list, description="Instrument short names")
    is_ongoing: bool = Field(default=False, description="Whether the collection is ongoing")
    native_id: str | None = Field(None, description="The native ID of the collection record")
    platforms: list[str] = Field(default_factory=list, description="Platform short names")
    processing_level_id: str | None = Field(None, description="Processing level (e.g., L3, L4)")
    provider_id: str | None = Field(None, description="The provider ID of the collection")
    related_urls: list[dict[str, Any]] = Field(
        default_factory=list, description="List of related URLs (e.g., documentation, guides)"
    )
    revision_id: int | None = Field(None, description="The revision ID of the collection metadata")
    science_keywords: list[dict[str, Any]] = Field(
        default_factory=list,
        description="GCMD science keyword hierarchy (Category/Topic/Term/VariableLevel)",
    )
    short_name: str | None = Field(None, description="Collection short name")
    spatial_resolution: str | None = Field(None, description="Human-readable spatial resolution")
    temporal_resolution: str | None = Field(None, description="Human-readable temporal resolution")
    time_end: datetime | None = Field(None, description="End of temporal coverage")
    time_start: datetime | None = Field(None, description="Start of temporal coverage")
    version: str | None = Field(None, description="Collection version")


class GetCollectionsInput(BaseModel):
    """Input model for get_collections."""

    model_config = ConfigDict(extra="forbid")

    keyword: KeywordParam = None
    concept_id: ConceptIdParam = None
    short_name: ShortNameParam = None
    provider: ProviderParam = None
    temporal_start_date: TemporalStartDateParam = None
    temporal_end_date: TemporalEndDateParam = None
    spatial_wkt_geometry: SpatialWktGeometryParam = None
    platform: PlatformParam
    instrument: InstrumentParam
    processing_level_id: ProcessingLevelIdParam
    has_granules: HasGranulesParam = None
    limit: LimitParam = 10
    cursor: CursorParam = None
    fields: FieldsParam


class GetCollectionsOutput(BaseCmrSearchOutput):
    """Output model for get_collections."""

    collections: list[CollectionResult] = Field(
        default_factory=list, description="Normalized collection results mapped from UMM-C"
    )
    next_cursor: str | None = Field(
        default=None, description="Pagination token for the next page of results"
    )
