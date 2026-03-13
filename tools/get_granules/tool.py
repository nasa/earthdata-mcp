"""Direct CMR granule search tool."""

import logging

from langfuse import observe

from models.tools.cmr_search import SearchStatus
from models.tools.get_granules import (
    CollectionConceptIdParam,
    GetGranulesInput,
    GetGranulesOutput,
    PageSizeParam,
    SearchAfterParam,
    SpatialWktGeometryParam,
    TemporalEndDateParam,
    TemporalStartDateParam,
)
from util.cmr.client import CMRError, search_cmr
from util.cmr.search_tools import build_spatial_files, format_temporal_range, normalize_granule_item

logger = logging.getLogger(__name__)


@observe(name="get_granules")
def get_granules(  # pylint: disable=too-many-arguments,unused-argument
    collection_concept_id: CollectionConceptIdParam,
    temporal_start_date: TemporalStartDateParam = None,
    temporal_end_date: TemporalEndDateParam = None,
    spatial_wkt_geometry: SpatialWktGeometryParam = None,
    page_size: PageSizeParam = 10,
    search_after: SearchAfterParam = None,
) -> dict:
    """Search CMR granules for a single parent collection.

    When checking data availability for a specific time period or geographic area, always
    provide temporal_start_date/temporal_end_date and/or spatial_wkt_geometry. Without these
    filters the results reflect the entire collection archive and total_hits will be non-zero
    even when no granules exist for the area or period the user cares about.
    """
    try:
        params = GetGranulesInput(**locals())

        search_params: dict[str, object] = {"collection_concept_id": params.collection_concept_id}

        temporal = format_temporal_range(params.temporal_start_date, params.temporal_end_date)
        if temporal:
            search_params["temporal"] = temporal

        files = build_spatial_files(params.spatial_wkt_geometry)
        method = "POST" if files else "GET"
        page = next(
            search_cmr(
                concept_type="granule",
                search_params=search_params,
                page_size=params.page_size,
                search_after=params.search_after,
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
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.exception("Unexpected granule search failure")
        return GetGranulesOutput(
            status=SearchStatus.ERROR,
            error_message=str(exc),
        ).model_dump()

    if page is None:
        return GetGranulesOutput(status=SearchStatus.NO_RESULTS).model_dump()

    granules = [normalize_granule_item(item) for item in page.items]
    status = SearchStatus.SUCCESS if granules else SearchStatus.NO_RESULTS
    return GetGranulesOutput(
        status=status,
        granules=granules,
        total_hits=page.total_hits,
        page_size=page.page_size,
        search_after=page.search_after,
        took_ms=page.took_ms,
    ).model_dump()
