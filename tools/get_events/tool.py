"""Query EONET for natural events."""

import logging

import requests
from langfuse import observe

from models.pagination import (
    LimitParam,
)
from models.tools.cmr_search import SearchStatus
from models.tools.get_events import (
    GetEventsInput,
    GetEventsOutput,
    EventResult,
    GeoJSONResult,
    CategoryResult,
    LayerResult
)
from util.eonet.client import (
    EONET_BASE_URL,
    EONETError,
    categories,
    events,
    get_request_url,
    layers,
)
from util.langfuse import trace_update


class Endpoints:
    """Available EONET API endpoints."""
    EVENTS = "events"
    GEOJSON = "events/geojson"
    CATEGORIES = "categories"
    LAYERS = "layers"


logger = logging.getLogger(__name__)


@observe(name="get_events")
def get_events(
    endpoint: str,
    params: dict = {},
    limit: LimitParam = 50,
    category: str = ""
) -> dict:
    """Send a request to the EONET API to retrieve event data based on specified parameters.
    
    This tool takes an EONET API endpoint name, list of parameters, and a results limit,
    sending a request with this information to the given endpoint. It then returns the
    results of the API call.
    """
    trace_update(
        tags=["eonet", "eventsapi"],
        metadata={
            "endpoint": endpoint,
            "params": params,
        },
    )

    try:
        eonet_params = GetEventsInput(
            endpoint=endpoint,
            params=params,
            limit=limit,
            category=category
        )
    except (ValueError, TypeError) as exc:
        logger.warning("get_events input validation failed: %s", exc)
        return GetEventsOutput(
            status=SearchStatus.ERROR,
            error_message=str(exc),
            title=SearchStatus.ERROR,
            link="",
        ).model_dump()

    endpoint = eonet_params.endpoint
    params = eonet_params.params
    if "limit" not in params:
        params["limit"] = limit
    category = eonet_params.category

    if not endpoint:
        return GetEventsOutput(
            status=SearchStatus.ERROR,
            error_message="Endpoint cannot be empty.",
            title=SearchStatus.ERROR,
            link=f"{EONET_BASE_URL}/",
        ).model_dump()

    try:
        if endpoint == Endpoints.EVENTS:
            results = events(params, False)
            if len(results["events"]) == 0:
                return GetEventsOutput(
                    status=SearchStatus.NO_RESULTS,
                    error_message=None,
                    title=results["title"],
                    link=results["link"],
                ).model_dump()
        elif endpoint == Endpoints.GEOJSON:
            results = events(params, True)
            if len(results["features"]) == 0:
                return GetEventsOutput(
                    status=SearchStatus.NO_RESULTS,
                    error_message=None,
                    title=SearchStatus.NO_RESULTS,
                    link="No link available.",
                ).model_dump()
        elif endpoint == Endpoints.CATEGORIES:
            results = categories(category, params)
            if len(results["events"]) == 0:
                return GetEventsOutput(
                    status=SearchStatus.NO_RESULTS,
                    error_message=None,
                    title=results["title"],
                    link=results["link"],
                ).model_dump()
        else:
            results = layers(category)
            if len(results["categories"]) == 0:
                return GetEventsOutput(
                    status=SearchStatus.NO_RESULTS,
                    error_message=None,
                    title=results["title"],
                    link=results["link"],
                ).model_dump()
    except EONETError as e:
        logger.error("EONET API request failed: %s", e)
        return GetEventsOutput(
            status=SearchStatus.ERROR,
            error_message=f"EONET could not process the request: {e}",
            title=SearchStatus.ERROR,
            link=f"{get_request_url()}",
        ).model_dump()

    total_hits = len(results)
    events = []
    for event in results:
        events.append(
            EventResult(
                id=event.get("id"),
                title=event.get("title"),
                metadata=event.get("metadata", {}),
                description=event.get("description"),
            )
        )

    response_dict = GetEventsOutput(
        status=SearchStatus.SUCCESS,
        total_hits=total_hits,
        error_message=None,
        events=events,
    ).model_dump()

    return response_dict
