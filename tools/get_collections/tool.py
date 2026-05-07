"""Direct CMR collection search tool."""

import logging

from langfuse import observe

from models.pagination import (
    MANDATORY_FIELDS_COLLECTIONS,
    CursorParam,
    LimitParam,
)
from models.tools.cmr_search import SearchStatus
from models.tools.get_collections import (
    ConceptIdParam,
    GetCollectionsInput,
    GetCollectionsOutput,
    HasGranulesParam,
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
from util.pagination import apply_field_filter, encode_cursor, resolve_cursor

logger = logging.getLogger(__name__)


@observe(name="get_collections")
def get_collections(  # pylint: disable=too-many-arguments,too-many-locals
    keyword: KeywordParam = None,
    concept_id: ConceptIdParam = None,
    short_name: ShortNameParam = None,
    provider: ProviderParam = None,
    temporal_start_date: TemporalStartDateParam = None,
    temporal_end_date: TemporalEndDateParam = None,
    spatial_wkt_geometry: SpatialWktGeometryParam = None,
    platform: list[str] | None = None,
    instrument: list[str] | None = None,
    processing_level_id: list[str] | None = None,
    has_granules: HasGranulesParam = None,
    limit: LimitParam = 10,
    cursor: CursorParam = None,
    fields: list[str] | None = None,
) -> dict:
    """Search CMR collections and return normalized results with pagination.

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

    Pagination: use limit (default 10, max 50) and cursor to page through results.
    Pass the next_cursor from a previous response as cursor to advance to the next page.
    Use fields to restrict which keys are returned per item and reduce response size.
    Cursors are query-scoped: they lock in the original search parameters and cannot be reused
    across different tools or different queries. To change search parameters, start a new search
    without a cursor.
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
            platform=platform or [],
            instrument=instrument or [],
            processing_level_id=processing_level_id or [],
            has_granules=has_granules,
            limit=limit,
            cursor=cursor,
            fields=fields or [],
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
        if params.platform:
            search_params["platform[]"] = params.platform
        if params.instrument:
            search_params["instrument[]"] = params.instrument
        if params.processing_level_id:
            search_params["processing_level_id[]"] = params.processing_level_id
        if params.has_granules is not None:
            search_params["has_granules"] = params.has_granules

        temporal = format_temporal_range(params.temporal_start_date, params.temporal_end_date)
        if temporal:
            search_params["temporal"] = temporal

        search_after = None
        files = None
        method = "GET"
        if params.cursor:
            cursor_value = resolve_cursor(params.cursor, "cmr")
            search_after = cursor_value.get("token")
            cursor_params = cursor_value.get("params", {})
            spatial_wkt = cursor_value.get("spatial")

            normalized_search = {k: v for k, v in search_params.items() if v}
            for k, v in normalized_search.items():
                if isinstance(v, list):
                    normalized_search[k] = sorted(v)

            normalized_cursor = {k: v for k, v in cursor_params.items() if v}
            for k, v in normalized_cursor.items():
                if isinstance(v, list):
                    normalized_cursor[k] = sorted(v)

            if normalized_search != normalized_cursor or spatial_wkt != params.spatial_wkt_geometry:
                return GetCollectionsOutput(
                    status=SearchStatus.ERROR,
                    error_message="Cursor parameters are query-scoped. You cannot change search parameters when paginating.",
                    next_cursor=None,
                ).model_dump()

            if spatial_wkt:
                files = build_spatial_files(spatial_wkt)
                method = "POST"

            # replace current params with original ones used in the cursor
            search_params = cursor_value.get("params", {})
        else:
            files = build_spatial_files(params.spatial_wkt_geometry)
            method = "POST" if files else "GET"
        page = next(
            search_cmr(
                concept_type="collection",
                search_params=search_params,
                page_size=params.limit,
                search_after=search_after,
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
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception("Unexpected error during collection search")
        return GetCollectionsOutput(
            status=SearchStatus.ERROR,
            error_message="An unexpected internal error occurred during collection search.",
        ).model_dump()

    if page is None:
        return GetCollectionsOutput(status=SearchStatus.NO_RESULTS).model_dump()

    collections = [normalize_collection_item(item) for item in page.items]
    status = SearchStatus.SUCCESS if collections else SearchStatus.NO_RESULTS
    cursor_payload = {"token": page.search_after, "params": search_params}
    if files:
        cursor_payload["spatial"] = (
            params.spatial_wkt_geometry if not params.cursor else cursor_value.get("spatial")
        )
    next_cursor = (
        encode_cursor("cmr", cursor_payload)
        if page.search_after and len(page.items) == params.limit
        else None
    )
    response_dict = GetCollectionsOutput(
        status=status,
        collections=collections,
        total_hits=page.total_hits,
        next_cursor=next_cursor,
    ).model_dump()

    if params.fields:
        apply_field_filter(
            response_dict["collections"], params.fields, MANDATORY_FIELDS_COLLECTIONS
        )

    return response_dict
