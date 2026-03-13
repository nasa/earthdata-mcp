"""Direct CMR collection search tool."""

import logging

from langfuse import observe

from models.tools.cmr_search import SearchStatus
from models.tools.get_collections import (
    ConceptIdParam,
    GetCollectionsInput,
    GetCollectionsOutput,
    PageSizeParam,
    ProviderParam,
    QueryParam,
    SearchAfterParam,
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

logger = logging.getLogger(__name__)


@observe(name="get_collections")
def get_collections(  # pylint: disable=too-many-arguments,unused-argument
    query: QueryParam = None,
    concept_id: ConceptIdParam = None,
    short_name: ShortNameParam = None,
    provider: ProviderParam = None,
    temporal_start_date: TemporalStartDateParam = None,
    temporal_end_date: TemporalEndDateParam = None,
    spatial_wkt_geometry: SpatialWktGeometryParam = None,
    page_size: PageSizeParam = 10,
    search_after: SearchAfterParam = None,
) -> dict:
    """Search CMR collections and return a single normalized results page.

    Unfiltered searches are supported and return a broad page of collections.
    When the user's question involves a specific time period or geographic area, always include
    temporal_start_date/temporal_end_date and/or spatial_wkt_geometry. A keyword-only search
    returns collections whose metadata mentions the terms but whose declared extent may be global
    or multi-decadal — presence in results does not confirm data exists for a specific region or
    period. Use filters here, then confirm actual granule availability with get_granules.
    """
    try:
        params = GetCollectionsInput(**locals())

        search_params: dict[str, object] = {}
        if params.query:
            search_params["keyword"] = params.query
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
                page_size=params.page_size,
                search_after=params.search_after,
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
        logger.exception("Unexpected collection search failure")
        return GetCollectionsOutput(
            status=SearchStatus.ERROR,
            error_message=str(exc),
        ).model_dump()

    if page is None:
        return GetCollectionsOutput(status=SearchStatus.NO_RESULTS).model_dump()

    collections = [normalize_collection_item(item) for item in page.items]
    status = SearchStatus.SUCCESS if collections else SearchStatus.NO_RESULTS
    return GetCollectionsOutput(
        status=status,
        collections=collections,
        total_hits=page.total_hits,
        page_size=page.page_size,
        search_after=page.search_after,
        took_ms=page.took_ms,
    ).model_dump()
