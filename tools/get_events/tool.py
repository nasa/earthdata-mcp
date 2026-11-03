"""Query EONET for natural events."""

import logging

from fastmcp.exceptions import ToolError
from langfuse import observe
from pydantic import ValidationError

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
    EONETError,
    categories,
    events,
    get_request_url,
    layers,
)
from util.langfuse import trace_update


DEFAULT_LIMIT: LimitParam = 5


logger = logging.getLogger(__name__)


def _build_response(endpoint: str, results: dict) -> dict:
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
                                else:
                                    if (type(event_category["layers"]) != str) or (type(event_category["layers"]) != list):
                                        raise EONETError("Unexpected layers results shape: Event category's 'layers' key is not a string or list")
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
                                        layers=None,
                                    )
                                )
                        event_list.append(
                            EventResult(
                                id=event["id"],
                                title=event["title"] if "title" in event else "",
                                description=event["description"] if "description" in event else "",
                                link=event["link"] if "link" in event else "",
                                closed=event["closed"] if "closed" in event else None,
                                categories=event_category_list if event_category_list != [] else [],
                                sources=event["sources"] if "sources" in event else [],
                                geometry=event["geometry"] if "geometry" in event else [],
                            )
                        )
                    else:
                        raise EONETError("Unexpected events results shape: No 'categories' key in event item")
                return GetEventsOutput(
                    status=SearchStatus.SUCCESS if event_list != [] else SearchStatus.NO_RESULTS,
                    error_message=None,
                    title=results["title"] if "title" in results else "",
                    description=results["description"] if "description" in results else "",
                    link=results["link"] if "link" in results else "",
                    type="",
                    events=event_list if event_list != [] else [],
                    features=[],
                    categories=[],
                ).model_dump()
            elif "categories" in results:
                return GetEventsOutput(
                    status=SearchStatus.SUCCESS,
                    error_message=None,
                    title=results["title"] if "title" in results else "",
                    description=results["description"] if "description" in results else "",
                    link=results["link"] if "link" in results else "",
                    type="",
                    events=[],
                    features=[],
                    categories=results["categories"],
                ).model_dump()
            else:
                raise EONETError("Unexpected events or categories results shape: No 'events' or 'categories' key in EONET response")
        elif endpoint == Endpoints.GEOJSON:
            feature_list = []
            if "features" in results:
                for feature in results["features"]:
                    try:
                        feature_list.append(
                            GeoJSONResult(
                                type=feature["type"],
                                properties=feature["properties"],
                                geometry=feature["geometry"],
                            )
                        )
                    except KeyError as e:
                        raise EONETError(f"Unexpected geojson results shape: Malformed GeoJSON: {e}")
                if "type" not in results:
                    raise EONETError("Unexpected geojson results shape: No 'type' key in EONET response")
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
                raise EONETError("Unexpected geojson results shape: No 'features' key in EONET response")
        elif endpoint == Endpoints.LAYERS:
            found_layers = False
            if "categories" in results:
                category_list = []
                for category in results["categories"]:
                    if "layers" in category:
                        category_layer_list = []
                        category_layer_string = ""
                        if type(category["layers"]) == list:
                            if len(category["layers"]) != 0:
                                found_layers = True
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
                            if category["layers"] != "":
                                found_layers = True
                                category_layer_string = category["layers"]
                        else:
                            raise EONETError("Unexpected layers results shape: Category's 'layers' key is not a string or list")
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
                                layers=None,
                            )
                        )
            return GetEventsOutput(
                status=SearchStatus.SUCCESS if found_layers else SearchStatus.NO_RESULTS,
                error_message=None,
                title=results["title"] if "title" in results else "",
                description=results["description"] if "description" in results else "",
                link=results["link"] if "link" in results else "",
                type="",
                events=[],
                features=[],
                categories=category_list if category_list != [] else [],
            ).model_dump()
        else:
            raise EONETError(f"Couldn't retrieve results. Endpoint does not exist: {get_request_url()}")
    except (ValueError, TypeError, EONETError) as e:
        logger.error("Results could not be saved: %s", e)
        raise ToolError(f"Attempted to store malformed results: {e}") from e


@observe(name="get_events")
def get_events(
    endpoint: str,
    params: dict = {},
    category: str = "",
) -> dict:
    """Send a request to the EONET API to retrieve event data based on specified parameters.
    
    This tool takes an EONET API endpoint name, list of parameters, and optional 
    category ID, sending a request with this information to the given endpoint. 
    It then returns the results of the API request.
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
            params=params,
            category=category,
        )
    except (ValidationError) as e:
        logger.warning("get_events input validation failed: %s", e)
        raise ToolError(f"Provided input is invalid: {str(e)}") from e

    endpoint = eonet_params.endpoint
    params = eonet_params.params
    category = eonet_params.category
    if "limit" not in params:
        params["limit"] = DEFAULT_LIMIT

    try:
        if endpoint == Endpoints.EVENTS:
            results = events(params, False)
        elif endpoint == Endpoints.GEOJSON:
            results = events(params, True)
        elif endpoint == Endpoints.CATEGORIES:
            results = categories(category, params)
            if ("categories" in results) and (len(results["categories"]) == 0):
                raise EONETError("No category provided to categories endpoint, but 'categories' key was empty")
        else:
            results = layers(category)
        return _build_response(endpoint, results)
    except EONETError as e:
        logger.error("EONET API request failed: %s", e)
        raise ToolError(f"Could not retrieve results from EONET: {e}") from e
