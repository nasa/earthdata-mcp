"""Query EONET for natural events."""

import logging

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


def _build_response_dict(endpoint: str, results: dict):
    try:
        if (endpoint == Endpoints.EVENTS) or (endpoint == Endpoints.CATEGORIES):
            event_list = []
            for event in results["events"]:
                event_list.append(
                    EventResult(
                        id=event["id"],
                        title=event["title"],
                        description=event["description"],
                        link=event["link"],
                        closed=event["closed"],
                        categories=event["categories"],
                        sources=event["sources"],
                        geometry=event["geometry"],
                    )
                )
            return GetEventsOutput(
                status=SearchStatus.SUCCESS,
                error_message=None,
                title=results["title"],
                description=results["description"],
                link=results["link"],
                events=event_list,
            ).model_dump()
        elif endpoint == Endpoints.GEOJSON:
            feature_list = []
            for feature in results["features"]:
                feature_list.append(
                    GeoJSONResult(
                        type=feature["type"],
                        properties=feature["properties"],
                        geometry=feature["geometry"],
                    )
                )
            return GetEventsOutput(
                status=SearchStatus.SUCCESS,
                error_message=None,
                type=results["type"],
                features=feature_list,
            ).model_dump()
        elif endpoint == Endpoints.LAYERS:
            category_list = []
            for category in results["categories"]:
                category_list.append(
                    CategoryResult(
                        id=category["id"],
                        title=category["title"],
                        layers=category["layers"],
                    )
                )
            return GetEventsOutput(
                status=SearchStatus.SUCCESS,
                error_message=None,
                title=results["title"],
                description=results["description"],
                link=results["link"],
                categories=category_list,
            ).model_dump()
        else:
            return GetEventsOutput(
                status=SearchStatus.ERROR,
                error_message=f"Couldn't retrieve results. Endpoint does not exist: {get_request_url()}",
                title=SearchStatus.ERROR,
                link=f"{get_request_url()}"
            )
    except (ValueError, TypeError) as e:
        logger.error("Results could not be saved: %s", e)
        return GetEventsOutput(
            status=SearchStatus.ERROR,
            error_message=f"Attempted to store malformed results: {e}",
            title=SearchStatus.ERROR,
            link=f"{get_request_url()}",
        ).model_dump()


@observe(name="get_events")
def get_events(
    endpoint: str,
    params: dict = {},
    category: str = "",
    limit: LimitParam = 5,
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
            "category": category,
            "params": params,
        },
    )

    try:
        eonet_params = GetEventsInput(
            endpoint=endpoint,
            category=category,
            params=params,
            limit=limit,
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
    category = eonet_params.category
    params = eonet_params.params
    if "limit" not in params:
        params["limit"] = eonet_params.limit

    if not endpoint:
        return GetEventsOutput(
            status=SearchStatus.ERROR,
            error_message="Endpoint cannot be empty.",
            title=SearchStatus.ERROR,
            link=f"{EONET_BASE_URL}/{endpoint}",
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
                    description=results["description"],
                    events=results["events"],
                ).model_dump()
        elif endpoint == Endpoints.GEOJSON:
            results = events(params, True)
            if len(results["features"]) == 0:
                return GetEventsOutput(
                    status=SearchStatus.NO_RESULTS,
                    error_message=None,
                    type=results["type"],
                    features=results["features"],
                ).model_dump()
        elif endpoint == Endpoints.CATEGORIES:
            results = categories(category, params)
            if len(results["events"]) == 0:
                return GetEventsOutput(
                    status=SearchStatus.NO_RESULTS,
                    error_message=None,
                    title=results["title"],
                    link=results["link"],
                    description=results["description"],
                    events=results["events"],
                ).model_dump()
        elif endpoint == Endpoints.LAYERS:
            results = layers(category)
            if len(results["categories"]) == 0:
                return GetEventsOutput(
                    status=SearchStatus.NO_RESULTS,
                    error_message=None,
                    title=results["title"],
                    link=results["link"],
                    description=results["description"],
                    categories=results["categories"],
                ).model_dump()
        else:
            return GetEventsOutput(
                status=SearchStatus.ERROR,
                error_message=f"The given endpoint does not exist: {get_request_url()}",
                title=SearchStatus.ERROR,
                link=f"{get_request_url()}"
            )
    except EONETError as e:
        logger.error("EONET API request failed: %s", e)
        return GetEventsOutput(
            status=SearchStatus.ERROR,
            error_message=f"EONET could not process the request: {e}",
            title=SearchStatus.ERROR,
            link=f"{get_request_url()}",
            description="Failed EONET API request",
        ).model_dump()

    return _build_response_dict(endpoint, results)
