"""Harmony submit transformation job tool."""

import logging
import dateutil.parser
import harmony

from langfuse import observe
from fastmcp.server.dependencies import get_access_token
from models.tools.submit_transformation_job import SubmitTransformationJobInput
from models.tools.get_transformation_job_status import GetTransformationJobStatusOutput
from util.harmony.client import get_client
from util.langfuse import trace_update

logger = logging.getLogger(__name__)


@observe(name="submit_transformation_job")
def submit_transformation_job(  # pylint: disable=too-many-arguments, disable=redefined-builtin
    collection_concept_id: str,
    bbox: list[float] | None = None,
    shape: str | None = None,
    temporal_start: str | None = None,
    temporal_stop: str | None = None,
    variables: list[str] | None = None,
    format: str | None = None,
    crs: str | None = None,
    width: int | None = None,
    height: int | None = None,
    max_results: int | None = None,
    granule_ids: list[str] | None = None,
) -> dict:
    """Submit a Harmony data processing request (subset/reformat/reproject).

    collection_concept_id is a CMR concept id (from search_collections). bbox is
    [west, south, east, north] in degrees. shape is a local path to a
    supported Harmony shapefile-subsetting file (.zip/.shz/.json/.geojson/.kml).
    temporal_start/temporal_stop are ISO 8601 timestamps. Check
    get_transformation_options first to confirm which of these parameters
    the collection's services actually support.

    granule_ids is an optional list of specific CMR granule concept IDs to process.

    Use a shapefile instead of a bounding box if one is available. The shapefile
    should have no more than 5000 points.

    Returns the new job's id and initial status. Poll with get_transformation_job_status,
    the resulting files will be available via the links field.

    If this tool fails because the requested combination of operations is unsupported, 
    suggest that the user call the get_transformation_options tool.
    """
    trace_update(
        tags=["harmony", "submit_request"],
        metadata={
            "collection_concept_id": collection_concept_id,
            "bbox": bbox,
            "shape": shape,
            "temporal_start": temporal_start,
            "temporal_stop": temporal_stop,
            "granule_id_count": len(granule_ids) if granule_ids else None,
            "variables": variables,
            "format": format,
            "crs": crs,
            "width": width,
            "height": height,
            "max_results": max_results,
        },
    )

    # Validate Input via Pydantic
    try:
        SubmitTransformationJobInput(
            collection_id=collection_concept_id,
            bbox=bbox,
            shape=shape,
            temporal_start=temporal_start,
            temporal_stop=temporal_stop,
            variables=variables,
            format=format,
            crs=crs,
            width=width,
            height=height,
            max_results=max_results,
            granule_ids=granule_ids,
        )
    except (ValueError, TypeError) as exc:
        logger.warning("submit_transformation_job input validation failed: %s", exc)
        return GetTransformationJobStatusOutput(
            code=type(exc).__name__,
            description=str(exc),
        ).model_dump()

    # Build Request Arguments
    request_kwargs: dict = {}

    if bbox is not None:
        if len(bbox) != 4:
            return GetTransformationJobStatusOutput(
                code="ValueError",
                description="bbox must have exactly 4 values: [west, south, east, north]",
            ).model_dump()
        request_kwargs["spatial"] = harmony.BBox(
            w=bbox[0], s=bbox[1], e=bbox[2], n=bbox[3]
        )

    if shape is not None:
        request_kwargs["shape"] = shape

    temporal: dict = {}
    try:
        if temporal_start:
            temporal["start"] = dateutil.parser.parse(temporal_start)
        if temporal_stop:
            temporal["stop"] = dateutil.parser.parse(temporal_stop)
    except dateutil.parser.ParserError as exc:
        logger.warning("submit_transformation_job temporal parsing failed: %s", exc)
        return GetTransformationJobStatusOutput(
            code="ParserError",
            description=f"Invalid date format: {str(exc)}",
        ).model_dump()

    if temporal:
        request_kwargs["temporal"] = temporal

    if variables is not None:
        request_kwargs["variables"] = variables
    if format is not None:
        request_kwargs["format"] = format
    if crs is not None:
        request_kwargs["crs"] = crs
    if width is not None:
        request_kwargs["width"] = width
    if height is not None:
        request_kwargs["height"] = height
    if max_results is not None:
        request_kwargs["max_results"] = max_results

    if granule_ids is not None:
        request_kwargs["granule_id"] = granule_ids

    # Always tag requests so they're identifiable as originating from this
    # MCP server (visible in the Harmony job's labels / request URL).
    request_kwargs["labels"] = ["harmony-mcp"]

    # Execute Harmony Submit Request
    try:
        request = harmony.Request(
            collection=harmony.Collection(id=collection_concept_id), **request_kwargs
        )
        token = get_access_token().token
        client = get_client(token)
        job_id = client.submit(request)
        status = client.status(job_id)
    except Exception as exc:
        logger.error("Error submitting request to Harmony API: %s", exc, exc_info=True)
        return GetTransformationJobStatusOutput(
            code=type(exc).__name__,
            description=f"Failed to submit request to Harmony: {str(exc)}",
        ).model_dump()

    # Parse/validate the Harmony status response. job_id populates via the
    # "jobID" alias already present in status, so no manual injection needed.
    try:
        parsed = GetTransformationJobStatusOutput(**status)
        parsed.job_id = job_id
    except (ValueError, TypeError) as exc:
        logger.error(
            "Harmony submit response did not match expected schema: %s",
            exc,
            exc_info=True,
        )
        return GetTransformationJobStatusOutput(
            code=type(exc).__name__,
            description=f"Unexpected response shape from Harmony: {exc}",
        ).model_dump()

    return parsed.model_dump(mode="json", by_alias=True)
