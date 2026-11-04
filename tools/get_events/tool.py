"""Query EONET for natural events."""

import logging

from langfuse import observe

from models.tools.cmr_search import SearchStatus
from models.tools.get_events import (
    ENDPOINTS,
    GetEventsInput,
    GetEventsOutput,
)
from util.eonet.client import (
    EONETError,
    events,
    get_request_url,
)
from util.langfuse import trace_update


logger = logging.getLogger(__name__)


def _build_response(endpoint: str, results: dict) -> dict:
    """Builds the response dict for the 'get_events' tool based on the endpoint and results from EONET."""
    try:
        if endpoint == ENDPOINTS.EVENTS:
            if ("events" in results) and (len(results["events"]) == 0):
                return GetEventsOutput(
                    status=SearchStatus.NO_RESULTS,
                    error_message=None,
                    title=results.get("title", "'get_events' Tool Results"),
                    description=results.get("description", "Results from '/events' EONET endpoint"),
                    link=results.get("link", f"{get_request_url()}"),
                    type="",
                    data=[],
                ).model_dump()
            elif ("events" in results) and (len(results["events"]) > 0):
                return GetEventsOutput(
                    status=SearchStatus.SUCCESS,
                    error_message=None,
                    title=results.get("title", "'get_events' Tool Results"),
                    description=results.get("description", "Results from '/events' EONET endpoint"),
                    link=results.get("link", f"{get_request_url()}"),
                    type="",
                    data=results["events"],
                ).model_dump()
            else:
                raise EONETError("Unexpected response shape for events request. Response did not contain 'events' key.")
        else:
            if (("features" in results) and ("type" in results)) and (len(results["features"]) == 0):
                return GetEventsOutput(
                    status=SearchStatus.NO_RESULTS,
                    error_message=None,
                    title=results.get("title", "'get_events' Tool Results"),
                    description=results.get("description", "Results from '/events/geojson' EONET endpoint"),
                    link=results.get("link", f"{get_request_url()}"),
                    type=results.get("type", "None"),
                    data=[],
                ).model_dump()
            elif (("features" in results) and ("type" in results)) and (len(results["features"]) > 0):
                return GetEventsOutput(
                    status=SearchStatus.SUCCESS,
                    error_message=None,
                    title=results.get("title", "'get_events' Tool Results"),
                    description=results.get("description", "Results from '/events/geojson' EONET endpoint"),
                    link=results.get("link", f"{get_request_url()}"),
                    type=results.get("type", "None"),
                    data=results["features"],
                ).model_dump()
            else:
                raise EONETError(
                    "Unexpected response shape for geojson request. Response did not contain 'features' and/or 'type' key."
                )
    except (ValueError, TypeError, EONETError) as e:
        logger.error("Results could not be saved: %s", e)
        return GetEventsOutput(
            status=SearchStatus.ERROR,
            error_message=str(e),
            title="'get_events' Tool Error",
            description="Attempted to store malformed results.",
            link=f"{get_request_url()}",
            type="",
            data=[],
        ).model_dump()


@observe(name="get_events")
def get_events(
    endpoint: str,
    params: dict = {},
) -> dict:
    """Send a request to the EONET API to retrieve event data based on specified parameters.
    
    This tool takes an EONET API endpoint name (events or events/geojson) and a list of parameters,
    sending a request to the specified endpoint with the given parameters. It returns the results
    formatted to contain the data itself and labels describing the data.
    """
    if (endpoint != ENDPOINTS.EVENTS) and (endpoint != ENDPOINTS.GEOJSON):
        logger.error(f"Provided endpoint does not exist or is not supported: '{endpoint}'")
        return GetEventsOutput(
            status=SearchStatus.ERROR,
            error_message=f"Provided endpoint does not exist or is not supported: '{endpoint}'",
            title="'get_events' Tool Error",
            description="Attempted to access invalid endpoint.",
            link="",
            type="",
            data=[],
        ).model_dump()
    
    trace_update(
        tags=["eonet", "eventsapi"],
        metadata={
            "endpoint": endpoint,
            "params": params,
        },
    )

    try:
        eonet_params = GetEventsInput(
            source=params.get("source", None),
            category=params.get("category", None),
            status=params.get("status", None),
            limit=params.get("limit", 5),
            days=params.get("days", None),
            start=params.get("start", None),
            end=params.get("end", None),
            magID=params.get("magID", None),
            magMin=params.get("magMin", None),
            magMax=params.get("magMax", None),
            bbox=params.get("bbox", None),
        )
    except (ValueError, TypeError) as e:
        logger.warning("get_events input validation failed: %s", e)
        return GetEventsOutput(
            status=SearchStatus.ERROR,
            error_message=str(e),
            title="'get_events' Tool Error",
            description="Input validation failed for get_events tool.",
            link="",
            type="",
            data=[],
        ).model_dump()

    endpoint = endpoint
    params = {
        "source": eonet_params.source,
        "category": eonet_params.category,
        "status": eonet_params.status,
        "limit": eonet_params.limit,
        "days": eonet_params.days,
        "start": eonet_params.start,
        "end": eonet_params.end,
        "magID": eonet_params.magID,
        "magMin": eonet_params.magMin,
        "magMax": eonet_params.magMax,
        "bbox": eonet_params.bbox,
    }

    try:
        if endpoint == ENDPOINTS.EVENTS:
            results = events(params, False)
        else:
            results = events(params, True)
    except (ValueError, TypeError, EONETError) as e:
        logger.error("EONET API request failed: %s", e)
        return GetEventsOutput(
            status=SearchStatus.ERROR,
            error_message=str(e),
            title="'get_events' Tool Error",
            description="Could not retrieve results from EONET.",
            link="",
            type="",
            data=[],
        ).model_dump()

    return _build_response(endpoint, results)
