"""Direct CMR granule search tool."""

import logging

from langfuse import observe

from models.tools.cmr_search import SearchStatus
from models.tools.get_granules import (
    CloudCoverMaxParam,
    CloudCoverMinParam,
    CollectionConceptIdParam,
    GetGranulesInput,
    GetGranulesOutput,
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

logger = logging.getLogger(__name__)


@observe(name="get_granules")
def get_granules(
    collection_concept_id: CollectionConceptIdParam,
    temporal_start_date: TemporalStartDateParam = None,
    temporal_end_date: TemporalEndDateParam = None,
    spatial_wkt_geometry: SpatialWktGeometryParam = None,
    cloud_cover_min: CloudCoverMinParam = None,
    cloud_cover_max: CloudCoverMaxParam = None,
) -> dict:
    """Search CMR granules for a single parent collection, returning up to 10 results.

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
        )

        search_params: dict[str, object] = {"collection_concept_id": params.collection_concept_id}

        temporal = format_temporal_range(params.temporal_start_date, params.temporal_end_date)
        if temporal:
            search_params["temporal"] = temporal

        cloud_cover = format_cloud_cover_range(params.cloud_cover_min, params.cloud_cover_max)
        if cloud_cover:
            search_params["cloud_cover"] = cloud_cover

        files = build_spatial_files(params.spatial_wkt_geometry)
        method = "POST" if files else "GET"
        page = next(
            search_cmr(
                concept_type="granule",
                search_params=search_params,
                page_size=10,
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
        logger.exception("Unexpected error during granule search: %s", exc)
        return GetGranulesOutput(
            status=SearchStatus.ERROR,
            error_message="An unexpected internal error occurred during granule search.",
        ).model_dump()

    if page is None:
        return GetGranulesOutput(status=SearchStatus.NO_RESULTS).model_dump()

    granules = [normalize_granule_item(item) for item in page.items]
    status = SearchStatus.SUCCESS if granules else SearchStatus.NO_RESULTS
    return GetGranulesOutput(
        status=status,
        granules=granules,
        total_hits=page.total_hits,
    ).model_dump()
