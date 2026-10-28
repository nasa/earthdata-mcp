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
    LayerResult,
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


DEFAULT_LIMIT: LimitParam = 5


logger = logging.getLogger(__name__)


def _build_response(endpoint: str, results: dict) -> GetEventsOutput:
    try:
        if (endpoint == Endpoints.EVENTS) or (endpoint == Endpoints.CATEGORIES):
            event_list = []
            event_category_list = []
            layer_list = []
            layer_string = ""
            if "events" in results:
                for event in results["events"]:
                    if "categories" in event:
                        for event_category in event["categories"]:
                            if "layers" in event_category:
                                if (type(event_category["layers"]) == list) and (len(event_category["layers"] != 0)):
                                    for layer in event_category["layers"]:
                                        layer_list.append(
                                            LayerResult(
                                                name=layer["name"] if "name" in layer else "",
                                                serviceUrl=layer["serviceUrl"] if "serviceUrl" in layer else None,
                                                serviceTypeId=layer["serviceTypeId"] if "serviceTypeId" in layer else None,
                                                parameters=layer["parameters"] if "parameters" in layer else None,
                                            )
                                        )
                                elif type(event_category["layers"]) == str:
                                    layer_string = event_category["layers"]
                                else:
                                    layer_list = None
                                    layer_string = None
                            event_category_list.append(
                                CategoryResult(
                                    id=event_category["id"] if "id" in event_category else "",
                                    title=event_category["title"] if "title" in event_category else None,
                                    link=event_category["link"] if "link" in event_category else None,
                                    description=event_category["description"] if "description" in event_category else None,
                                    layers=layer_list if type(event_category["layers"]) == list else layer_string,
                                )
                            )
                    event_list.append(
                        EventResult(
                            id=event["id"] if "id" in event else "",
                            title=event["title"] if "title" in event else None,
                            description=event["description"] if "description" in event else None,
                            link=event["link"] if "link" in event else None,
                            closed=event["closed"] if "closed" in event else None,
                            categories=event_category_list if event_category_list != [] else None,
                            sources=event["sources"] if "sources" in event else None,
                            geometry=event["geometry"] if "geometry" in event else None,
                        )
                    )
            return GetEventsOutput(
                status=SearchStatus.SUCCESS,
                error_message=None,
                title=results["title"],
                description=results["description"],
                link=results["link"],
                type="",
                events=event_list if event_list != [] else [],
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
                status=SearchStatus.SUCCESS,
                error_message=None,
                title="",
                description="",
                link="",
                type=results["type"],
                events=[],
                features=feature_list if feature_list != [] else [],
                categories=[],
            ).model_dump()
        elif endpoint == Endpoints.LAYERS:
            category_list = []
            category_layer_list = []
            category_layer_string = ""
            if "categories" in results:
                for category in results["categories"]:
                    if "layers" in category:
                        if (type(category["layers"]) == list) and (len(category["layers"] != 0)):
                            for layer in category["layers"]:
                                category_layer_list.append(
                                    LayerResult(
                                        name=layer["name"] if "name" in layer else "",
                                        serviceUrl=layer["serviceUrl"] if "serviceUrl" in layer else None,
                                        serviceTypeId=layer["serviceTypeId"] if "serviceTypeId" in layer else None,
                                        parameters=layer["parameters"] if "parameters" in layer else None,
                                    )
                                )
                        elif type(category["layers"]) == str:
                            category_layer_string = category["layers"]
                        else:
                            category_layer_list = None
                            category_layer_string = None
                    category_list.append(
                        CategoryResult(
                            id=category["id"] if "id" in category else None,
                            title=category["title"] if "title" in category else "",
                            link=None,
                            description=None,
                            layers=category_layer_list if type(category["layers"]) == list else category_layer_string,
                        )
                    )
            return GetEventsOutput(
                status=SearchStatus.SUCCESS,
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
) -> GetEventsOutput:
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
        )
    except (ValueError, TypeError) as e:
        logger.warning("get_events input validation failed: %s", e)
        raise EONETError(str(e)) from e

    endpoint = eonet_params.endpoint
    category = eonet_params.category
    params = eonet_params.params
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

    try:
        if endpoint == Endpoints.EVENTS:
            results = events(params, False)
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
            results = events(params, True)
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
            )
        response = _build_response(endpoint, results)
        if response.status == SearchStatus.ERROR:
            raise EONETError(response.error_message)
        else:
            return response
    except EONETError as e:
        logger.error("EONET API request failed: %s", e)
        return GetEventsOutput(
            status=SearchStatus.ERROR,
            error_message=f"EONET could not process the request: {e}",
            title=SearchStatus.ERROR,
            description="Failed EONET API request",
            link=f"{get_request_url()}",
            type="",
            events=[],
            features=[],
            categories=[],
        ).model_dump()
