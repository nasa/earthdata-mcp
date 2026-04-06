"""Direct CMR collection search tool."""

import logging

from langfuse import observe

from models.tools.cmr_search import SearchStatus
from models.tools.get_collections import (
    ConceptIdParam,
    GetCollectionsInput,
    GetCollectionsOutput,
    KeywordParam,
    ProviderParam,
    ShortNameParam,
    SpatialWktGeometryParam,
    TemporalEndDateParam,
    TemporalStartDateParam,
)
from util.cmr.client import CMRError, search_cmr
from util.cmr.search_tools import (
    build_spatial_files,
    format_temporal_range,
    normalize_collection_item,
)
from util.langfuse import trace_update

logger = logging.getLogger(__name__)


@observe(name="get_collections")
def get_collections(  # pylint: disable=too-many-arguments
    keyword: KeywordParam = None,
    concept_id: ConceptIdParam = None,
    short_name: ShortNameParam = None,
    provider: ProviderParam = None,
    temporal_start_date: TemporalStartDateParam = None,
    temporal_end_date: TemporalEndDateParam = None,
    spatial_wkt_geometry: SpatialWktGeometryParam = None,
) -> dict:
    """Search CMR collections and return up to 20 normalized results.

    Unfiltered searches are supported and return a broad set of collections sorted by usage.
    When the user's question involves a specific time period or geographic area, always include
    temporal_start_date/temporal_end_date and/or spatial_wkt_geometry. A keyword-only search
    returns collections whose metadata mentions the terms but whose declared extent may be global
    or multi-decadal — presence in results does not confirm data exists for a specific region or
    period. Use filters here, then confirm actual granule availability with get_granules.

    Keyword AND logic: CMR requires ALL space-separated words to appear somewhere in a
    collection's indexed metadata (title, summary, science keywords, instruments, etc.).
    Words do not need to be in the same field or adjacent. More words = stricter filter.
    Prefer 2–4 precise terms. If 0 results, drop the least essential word and retry.
    Phrase search: wrap value in escaped double quotes for exact sequence matching;
    cannot be mixed with standalone keywords.
    """
    metadata = {}
    if keyword:
        metadata["keyword"] = keyword
    if concept_id:
        metadata["concept_id"] = concept_id
    if short_name:
        metadata["short_name"] = short_name
    if provider:
        metadata["provider"] = provider
    if temporal_start_date:
        metadata["temporal_start_date"] = temporal_start_date
    if temporal_end_date:
        metadata["temporal_end_date"] = temporal_end_date
    if spatial_wkt_geometry:
        metadata["spatial_wkt_geometry"] = (
            spatial_wkt_geometry[:200] + "..."
            if len(spatial_wkt_geometry) > 200
            else spatial_wkt_geometry
        )

    trace_update(
        tags=["cmr", "collections"],
        metadata=metadata,
    )

    try:
        params = GetCollectionsInput(
            keyword=keyword,
            concept_id=concept_id,
            short_name=short_name,
            provider=provider,
            temporal_start_date=temporal_start_date,
            temporal_end_date=temporal_end_date,
            spatial_wkt_geometry=spatial_wkt_geometry,
        )

        search_params: dict[str, object] = {}
        if params.keyword:
            search_params["keyword"] = params.keyword
        if params.concept_id:
            search_params["concept_id"] = params.concept_id
        if params.short_name:
            search_params["short_name"] = params.short_name
        if params.provider:
            search_params["provider"] = params.provider

        temporal = format_temporal_range(params.temporal_start_date, params.temporal_end_date)
        if temporal:
            search_params["temporal"] = temporal

        files = build_spatial_files(params.spatial_wkt_geometry)
        method = "POST" if files else "GET"
        page = next(
            search_cmr(
                concept_type="collection",
                search_params=search_params,
                page_size=20,
                method=method,
                files=files,
            ),
            None,
        )
    except (CMRError, ValueError, TypeError) as exc:
        logger.warning("Collection search failed: %s", exc)
        return GetCollectionsOutput(
            status=SearchStatus.ERROR,
            error_message=str(exc),
        ).model_dump()
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.exception("Unexpected error during collection search: %s", exc)
        return GetCollectionsOutput(
            status=SearchStatus.ERROR,
            error_message="An unexpected internal error occurred during collection search.",
        ).model_dump()

    if page is None:
        return GetCollectionsOutput(status=SearchStatus.NO_RESULTS).model_dump()

    collections = [normalize_collection_item(item) for item in page.items]
    status = SearchStatus.SUCCESS if collections else SearchStatus.NO_RESULTS
    return GetCollectionsOutput(
        status=status,
        collections=collections,
        total_hits=page.total_hits,
    ).model_dump()
