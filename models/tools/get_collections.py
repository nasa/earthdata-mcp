"""Input and output models for the get_collections MCP tool."""

from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field

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
            "CMR returns any collection that touches this shape, so precise geometries are "
            "preferred to prevent false positives. Set this whenever the user specifies a geographic region "
            "— omitting it returns collections with global or unspecified coverage."
        )
    ),
]


class CollectionResult(BaseModel):
    """Minimal collection result for direct CMR-backed discovery."""

    abstract: str | None = Field(None, description="Collection summary or abstract")
    collection_data_type: str | None = Field(
        None, description="e.g., SCIENCE_QUALITY, NEAR_REAL_TIME"
    )
    concept_id: str = Field(..., description="CMR collection concept ID")
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


class GetCollectionsOutput(BaseCmrSearchOutput):
    """Output model for get_collections."""

    collections: list[CollectionResult] = Field(
        default_factory=list, description="Normalized collection results mapped from UMM-C"
    )
