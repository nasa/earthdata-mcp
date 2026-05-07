"""Direct CMR granule search tool."""

import logging

from langfuse import observe

from models.pagination import (
    MANDATORY_FIELDS_GRANULES,
    CursorParam,
    LimitParam,
)
from models.tools.cmr_search import SearchStatus
from models.tools.get_granules import (
    CloudCoverMaxParam,
    CloudCoverMinParam,
    CollectionConceptIdParam,
    DayNightFlagParam,
    GetGranulesInput,
    GetGranulesOutput,
    SortKeyParam,
    SpatialWktGeometryParam,
    TemporalEndDateParam,
    TemporalStartDateParam,
)
from util.cmr.client import CMRError, search_cmr
from util.cmr.search_tools import (
    build_spatial_files,
    format_cloud_cover_range,
    format_temporal_range,
    normalize_granule_item,
)
from util.langfuse import trace_update
from util.pagination import apply_field_filter, encode_cursor, resolve_cursor

logger = logging.getLogger(__name__)


@observe(name="get_granules")
def get_granules(  # pylint: disable=too-many-arguments,too-many-locals
    collection_concept_id: CollectionConceptIdParam,
    temporal_start_date: TemporalStartDateParam = None,
    temporal_end_date: TemporalEndDateParam = None,
    spatial_wkt_geometry: SpatialWktGeometryParam = None,
    cloud_cover_min: CloudCoverMinParam = None,
    cloud_cover_max: CloudCoverMaxParam = None,
    day_night_flag: DayNightFlagParam = None,
    sort_key: SortKeyParam = None,
    limit: LimitParam = 10,
    cursor: CursorParam = None,
    fields: list[str] | None = None,
) -> dict:
    """Search CMR granules for a single parent collection, returning paginated results.

    When checking data availability for a specific time period or geographic area, always
    provide temporal_start_date/temporal_end_date and/or spatial_wkt_geometry. Without these
    filters the results reflect the entire collection archive and total_hits will be non-zero
    even when no granules exist for the area or period the user cares about.

    Cloud cover filtering (cloud_cover_min/cloud_cover_max) is only meaningful for optical
    imagery collections that report per-granule cloud cover (e.g., Landsat, MODIS, VIIRS,
    Sentinel-2 via CMR). Do not set these for non-optical data such as SAR or altimetry.
    The CMR parameter format is cloud_cover=min,max (0–100).

    Data Access Note: Most granule download URLs require NASA Earthdata Login authentication.
    If you generate Python code for the user to download these granules, strongly recommend
    using the `earthaccess` Python library (https://earthaccess.readthedocs.io) as it
    automatically handles the complex OAuth authentication redirects.

    Pagination: use limit (default 10, max 50) and cursor to page through results.
    Pass the next_cursor from a previous response as cursor to advance to the next page.
    Use fields to restrict which keys are returned per item and reduce response size.
    Cursors are query-scoped: they lock in the original search parameters and cannot be reused
    across different tools or different queries. To change search parameters, start a new search
    without a cursor.
    """
    metadata = {
        "collection_concept_id": collection_concept_id,
    }
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
    if cloud_cover_min is not None:
        metadata["cloud_cover_min"] = cloud_cover_min
    if cloud_cover_max is not None:
        metadata["cloud_cover_max"] = cloud_cover_max

    trace_update(
        tags=["cmr", "granules"],
        metadata=metadata,
    )

    try:
        params = GetGranulesInput(
            collection_concept_id=collection_concept_id,
            temporal_start_date=temporal_start_date,
            temporal_end_date=temporal_end_date,
            spatial_wkt_geometry=spatial_wkt_geometry,
            cloud_cover_min=cloud_cover_min,
            cloud_cover_max=cloud_cover_max,
            day_night_flag=day_night_flag,
            sort_key=sort_key,
            limit=limit,
            cursor=cursor,
            fields=fields or [],
        )

        search_params: dict[str, object] = {"collection_concept_id": params.collection_concept_id}

        temporal = format_temporal_range(params.temporal_start_date, params.temporal_end_date)
        if temporal:
            search_params["temporal"] = temporal

        cloud_cover = format_cloud_cover_range(params.cloud_cover_min, params.cloud_cover_max)
        if cloud_cover:
            search_params["cloud_cover"] = cloud_cover

        if params.day_night_flag:
            search_params["day_night_flag"] = params.day_night_flag
        if params.sort_key:
            search_params["sort_key"] = params.sort_key

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
                return GetGranulesOutput(
                    status=SearchStatus.ERROR,
                    error_message="Cursor parameters are query-scoped. You cannot change search parameters when paginating.",
                    next_cursor=None,
                ).model_dump()

            search_params = cursor_value.get("params", {})
            if spatial_wkt:
                files = build_spatial_files(spatial_wkt)
                method = "POST"
        else:
            files = build_spatial_files(params.spatial_wkt_geometry)
            method = "POST" if files else "GET"
        page = next(
            search_cmr(
                concept_type="granule",
                search_params=search_params,
                page_size=params.limit,
                search_after=search_after,
                method=method,
                files=files,
            ),
            None,
        )
    except (CMRError, ValueError, TypeError) as exc:
        logger.warning("Granule search failed: %s", exc)
        return GetGranulesOutput(
            status=SearchStatus.ERROR,
            error_message=str(exc),
        ).model_dump()
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception("Unexpected error during granule search")
        return GetGranulesOutput(
            status=SearchStatus.ERROR,
            error_message="An unexpected internal error occurred during granule search.",
        ).model_dump()

    if page is None:
        return GetGranulesOutput(status=SearchStatus.NO_RESULTS).model_dump()

    granules = [normalize_granule_item(item) for item in page.items]
    status = SearchStatus.SUCCESS if granules else SearchStatus.NO_RESULTS
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
    response_dict = GetGranulesOutput(
        status=status,
        granules=granules,
        total_hits=page.total_hits,
        next_cursor=next_cursor,
    ).model_dump()

    if params.fields:
        apply_field_filter(response_dict["granules"], params.fields, MANDATORY_FIELDS_GRANULES)

    return response_dict
