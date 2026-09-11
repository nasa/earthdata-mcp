import logging
import dateutil.parser
import harmony

from langfuse import observe
from models.tools.submit_request import SubmitRequestInput, SubmitRequestOutput
from util.harmony.client import get_client, _json_safe
from util.langfuse import trace_update
from fastmcp.server.dependencies import get_access_token

logger = logging.getLogger(__name__)


@observe(name="submit_request")
def submit_request(
    collection_id: str,
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

    collection_id is a CMR concept id (from search_collections). bbox is
    [west, south, east, north] in degrees. shape is a local path to a
    supported Harmony shapefile-subsetting file (.zip/.shz/.json/.geojson/.kml).
    temporal_start/temporal_stop are ISO 8601 timestamps. Check
    get_collection_capabilities first to confirm which of these parameters
    the collection's services actually support.
    
    granule_ids is an optional list of specific CMR granule concept IDs to process.

    Use a shapefile instead of a bounding box if one is available. The shapefile
    should have no more than 5000 points.

    Returns the new job's id and initial status. Poll with get_job_status
    or wait_for_job, then fetch files with download_job_results.
    """
    trace_update(
        tags=["harmony", "submit_request"],
        metadata={
            "collection_id": collection_id,
            "bbox": bbox,
            "shape": shape,
            "temporal_start": temporal_start,
            "temporal_stop": temporal_stop,
            "granule_ids": granule_ids,
        },
    )

    # Validate Input via Pydantic
    try:
        params = SubmitRequestInput(
            collection_id=collection_id,
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
        logger.warning("submit_request input validation failed: %s", exc)
        return SubmitRequestOutput(
            code=type(exc).__name__,
            description=str(exc)
        ).model_dump()

    # Build Request Arguments
    request_kwargs: dict = {}

    if bbox is not None:
        if len(bbox) != 4:
            return SubmitRequestOutput(
                code="ValueError",
                description="bbox must have exactly 4 values: [west, south, east, north]"
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
        logger.warning("submit_request temporal parsing failed: %s", exc)
        return SubmitRequestOutput(
            code="ParserError",
            description=f"Invalid date format: {str(exc)}"
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
            collection=harmony.Collection(id=collection_id), **request_kwargs
        )
        token = get_access_token().token
        client = get_client(token)
        job_id = client.submit(request)
        status = client.status(job_id)
        
    except Exception as exc:
        logger.error("Error submitting request to Harmony API: %s", exc, exc_info=True)
        return SubmitRequestOutput(
            code=type(exc).__name__,
            description=f"Failed to submit request to Harmony: {str(exc)}"
        ).model_dump()

    return {"job_id": job_id, **_json_safe(status)}