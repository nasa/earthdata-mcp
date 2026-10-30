"""Query EONET for natural events."""

import logging

from fastmcp.exceptions import ToolError
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
    LayerResult,
    Endpoints,
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


DEFAULT_LIMIT: LimitParam = 5


logger = logging.getLogger(__name__)


def _build_response(endpoint: str, results: dict, event_id_used: bool = False) -> dict:
    try:
        if (endpoint == Endpoints.EVENTS) or (endpoint == Endpoints.CATEGORIES):
            if "events" in results:
                event_list = []
                for event in results["events"]:
                    if "categories" in event:
                        event_category_list = []
                        for event_category in event["categories"]:
                            if "layers" in event_category:
                                layer_list = []
                                layer_string = ""
                                if (type(event_category["layers"]) == list) and (len(event_category["layers"]) != 0):
                                    for layer in event_category["layers"]:
                                        layer_list.append(
                                            LayerResult(
                                                name=layer["name"] if "name" in layer else "",
                                                serviceUrl=layer["serviceUrl"] if "serviceUrl" in layer else "",
                                                serviceTypeId=layer["serviceTypeId"] if "serviceTypeId" in layer else "",
                                                parameters=layer["parameters"] if "parameters" in layer else [],
                                            )
                                        )
                                elif type(event_category["layers"]) == str:
                                    layer_string = event_category["layers"]
                                event_category_list.append(
                                    CategoryResult(
                                        id=event_category["id"] if "id" in event_category else "",
                                        title=event_category["title"] if "title" in event_category else "",
                                        link=event_category["link"] if "link" in event_category else "",
                                        description=event_category["description"] if "description" in event_category else "",
                                        layers=layer_list if type(event_category["layers"]) == list else layer_string,
                                    )
                                )
                            else:
                                event_category_list.append(
                                    CategoryResult(
                                        id=event_category["id"] if "id" in event_category else "",
                                        title=event_category["title"] if "title" in event_category else "",
                                        link=event_category["link"] if "link" in event_category else "",
                                        description=event_category["description"] if "description" in event_category else "",
                                        layers=[],
                                    )
                                )
                        event_list.append(
                            EventResult(
                                id=event["id"] if "id" in event else "",
                                title=event["title"] if "title" in event else "",
                                description=event["description"] if "description" in event else "",
                                link=event["link"] if "link" in event else "",
                                closed=event["closed"] if "closed" in event else "",
                                categories=event_category_list if event_category_list != [] else [],
                                sources=event["sources"] if "sources" in event else [],
                                geometry=event["geometry"] if "geometry" in event else [],
                            )
                        )
                    else:
                        return GetEventsOutput(
                            status=SearchStatus.ERROR,
                            error_message="Unexpected events results shape: No 'categories' key in event item",
                            title=results["title"],
                            description=results["description"],
                            link=results["link"],
                            type="",
                            events=[],
                            features=[],
                            categories=[],
                        ).model_dump()
                return GetEventsOutput(
                    status=SearchStatus.SUCCESS if event_list != [] else SearchStatus.NO_RESULTS,
                    error_message=None,
                    title=results["title"],
                    description=results["description"],
                    link=results["link"],
                    type="",
                    events=event_list if event_list != [] else [],
                    features=[],
                    categories=[],
                ).model_dump()
            elif "categories" in results:
                return GetEventsOutput(
                    status=SearchStatus.SUCCESS,
                    error_message=None,
                    title=results["title"],
                    description=results["description"],
                    link=results["link"],
                    type="",
                    events=[],
                    features=[],
                    categories=results["categories"],
                ).model_dump()
            else:
                return GetEventsOutput(
                    status=SearchStatus.ERROR,
                    error_message="Unexpected events or categories results shape: No 'events' or 'categories' key in EONET response",
                    title=results["title"],
                    description=results["description"],
                    link=results["link"],
                    type="",
                    events=[],
                    features=[],
                    categories=[],
                ).model_dump()
        elif endpoint == Endpoints.GEOJSON:
            feature_list = []
            if "features" in results:
                for feature in results["features"]:
                    feature_list.append(
                        GeoJSONResult(
                            type=feature["type"] if "type" in feature else "",
                            properties=feature["properties"] if "properties" in feature else {},
                            geometry=feature["geometry"] if "geometry" in feature else {},
                        )
                    )
                return GetEventsOutput(
                    status=SearchStatus.SUCCESS if feature_list != [] else SearchStatus.NO_RESULTS,
                    error_message=None,
                    title="",
                    description="",
                    link="",
                    type=results["type"],
                    events=[],
                    features=feature_list if feature_list != [] else [],
                    categories=[],
                ).model_dump()
            else:
                return GetEventsOutput(
                    status=SearchStatus.ERROR,
                    error_message="Unexpected geojson results shape: No 'features' key in EONET response",
                    title=results["title"],
                    description=results["description"],
                    link=results["link"],
                    type="",
                    events=[],
                    features=[],
                    categories=[],
                ).model_dump()
        elif endpoint == Endpoints.LAYERS:
            found_layers = False
            if "categories" in results:
                category_list = []
                for category in results["categories"]:
                    if "layers" in category:
                        category_layer_list = []
                        category_layer_string = ""
                        if (type(category["layers"]) == list) and (len(category["layers"]) != 0):
                            for layer in category["layers"]:
                                category_layer_list.append(
                                    LayerResult(
                                        name=layer["name"] if "name" in layer else "",
                                        serviceUrl=layer["serviceUrl"] if "serviceUrl" in layer else "",
                                        serviceTypeId=layer["serviceTypeId"] if "serviceTypeId" in layer else "",
                                        parameters=layer["parameters"] if "parameters" in layer else [],
                                    )
                                )
                        elif type(category["layers"]) == str:
                            category_layer_string = category["layers"]
                        category_list.append(
                            CategoryResult(
                                id=category["id"] if "id" in category else "",
                                title=category["title"] if "title" in category else "",
                                link="",
                                description="",
                                layers=category_layer_list if type(category["layers"]) == list else category_layer_string,
                            )
                        )
                    else:
                        category_list.append(
                            CategoryResult(
                                id=category["id"] if "id" in category else "",
                                title=category["title"] if "title" in category else "",
                                link="",
                                description="",
                                layers=[],
                            )
                        )
            for cat in category_list:
                if (cat.layers != []) and (cat.layers != ""):
                    found_layers = True
            return GetEventsOutput(
                status=SearchStatus.SUCCESS if found_layers else SearchStatus.NO_RESULTS,
                error_message=None,
                title=results["title"],
                description=results["description"],
                link=results["link"],
                type="",
                events=[],
                features=[],
                categories=category_list if category_list != [] else [],
            ).model_dump()
        else:
            return GetEventsOutput(
                status=SearchStatus.ERROR,
                error_message=f"Couldn't retrieve results. Endpoint does not exist: {get_request_url()}",
                title=SearchStatus.ERROR,
                description="",
                link=f"{get_request_url()}",
                type="",
                events=[],
                features=[],
                categories=[],
            ).model_dump()
    except (ValueError, TypeError) as e:
        logger.error("Results could not be saved: %s", e)
        raise ToolError(f"Attempted to store malformed results: {e}") from e


@observe(name="get_events")
def get_events(
    endpoint: str,
    params: dict = {},
    event_id: str = "",
    category: str = "",
) -> dict:
    """Send a request to the EONET API to retrieve event data based on specified parameters.
    
    This tool takes an EONET API endpoint name, list of parameters, and optional 
    event/category IDs, sending a request with this information to the given endpoint. 
    It then returns the results of the API request.
    """
    trace_update(
        tags=["eonet", "eventsapi"],
        metadata={
            "endpoint": endpoint,
            "event_id": event_id,
            "category": category,
            "params": params,
        },
    )

    try:
        eonet_params = GetEventsInput(
            endpoint=endpoint,
            params=params,
            category=category,
            event_id=event_id,
        )
    except (ValueError, TypeError) as e:
        logger.warning("get_events input validation failed: %s", e)
        raise ToolError(str(e)) from e

    endpoint = eonet_params.endpoint
    params = eonet_params.params
    event_id = eonet_params.event_id
    category = eonet_params.category
    if "limit" not in params:
        params["limit"] = DEFAULT_LIMIT

    if not endpoint:
        return GetEventsOutput(
            status=SearchStatus.ERROR,
            error_message="Endpoint cannot be empty.",
            title=SearchStatus.ERROR,
            description="",
            link=f"{EONET_BASE_URL}/{endpoint}",
            type="",
            events=[],
            features=[],
            categories=[],
        ).model_dump()
    elif (endpoint != Endpoints.EVENTS) and event_id:
        return GetEventsOutput(
            status=SearchStatus.ERROR,
            error_message="An event ID can only be used with the `/events' endpoint.",
            title=SearchStatus.ERROR,
            description="",
            link=f"{EONET_BASE_URL}/{endpoint}/{event_id}",
            type="",
            events=[],
            features=[],
            categories=[],
        ).model_dump()

    try:
        if endpoint == Endpoints.EVENTS:
            results = events(params, event_id, False)
            if len(results["events"]) == 0:
                return GetEventsOutput(
                    status=SearchStatus.NO_RESULTS,
                    error_message=None,
                    title=results["title"],
                    description=results["description"],
                    link=results["link"],
                    type="",
                    events=results["events"],
                    features=[],
                    categories=[],
                ).model_dump()
        elif endpoint == Endpoints.GEOJSON:
            results = events(params, "", True) # geojson endpoint doesn't accept event IDs
            if len(results["features"]) == 0:
                return GetEventsOutput(
                    status=SearchStatus.NO_RESULTS,
                    error_message=None,
                    title="",
                    description="",
                    link="",
                    type=results["type"],
                    events=[],
                    features=results["features"],
                    categories=[],
                ).model_dump()
        elif endpoint == Endpoints.CATEGORIES:
            results = categories(category, params)
            if ("events" in results) and (len(results["events"]) == 0):
                return GetEventsOutput(
                    status=SearchStatus.NO_RESULTS,
                    error_message=None,
                    title=results["title"],
                    description=results["description"],
                    link=results["link"],
                    type="",
                    events=results["events"],
                    features=[],
                    categories=[],
                ).model_dump()
        elif endpoint == Endpoints.LAYERS:
            results = layers(category)
            if len(results["categories"]) == 0:
                return GetEventsOutput(
                    status=SearchStatus.NO_RESULTS,
                    error_message=None,
                    title=results["title"],
                    description=results["description"],
                    link=results["link"],
                    type="",
                    events=[],
                    features=[],
                    categories=results["categories"],
                ).model_dump()
        else:
            return GetEventsOutput(
                status=SearchStatus.ERROR,
                error_message=f"The given endpoint does not exist: {get_request_url()}",
                title=SearchStatus.ERROR,
                description="",
                link=f"{get_request_url()}",
                type="",
                events=[],
                features=[],
                categories=[],
            ).model_dump()
        response = _build_response(endpoint, results)
        if response["status"] == SearchStatus.ERROR:
            raise EONETError(response["error_message"])
        else:
            return response
    except EONETError as e:
        logger.error("EONET API request failed: %s", e)
        raise ToolError(f"Failed to communicate with EONET API: {e}") from e
