"""Query EONET for natural events."""

import logging

import requests
from langfuse import observe

from models.pagination import (
    LimitParam,
)
from models.tools.cmr_search import SearchStatus
from models.tools.get_events import GetEventsInput, GetEventsOutput, EventResult
from util.langfuse import trace_update

logger = logging.getLogger(__name__)


@observe(name="get_events")
def get_events(
    endpoint: str,
    event_params: dict | None = None,
    limit: LimitParam = 10
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
            "params": event_params,
        },
    )

    try:
        request = GetEventsInput(
            endpoint=endpoint,
            event_params=event_params or {},
            limit=limit,
        )
    except (ValueError, TypeError) as exc:
        logger.warning("get_events input validation failed: %s", exc)
        return GetEventsOutput(
            status=SearchStatus.ERROR,
            total_hits=0,
            error_message=str(exc),
            events=[],
        ).model_dump()

    endpoint = request.endpoint
    event_params = request.event_params

    if endpoint:
        url = f"https://eonet.gsfc.nasa.gov/api/{endpoint}"
        request_params = event_params
    else:
        return GetEventsOutput(
            status=SearchStatus.ERROR,
            total_hits=0,
            error_message="Endpoint cannot be empty.",
            events=[],
        ).model_dump()

    try:
        response = requests.get(url, params=request_params)
        response.raise_for_status()
        results = response.json()
    except requests.RequestException as exc:
        logger.error("EONET API request failed: %s", exc)
        return GetEventsOutput(
            status=SearchStatus.ERROR,
            total_hits=0,
            error_message=f"EONET could not process the request: {exc}",
            events=[],
        ).model_dump()

    if len(results) == 0:
        return GetEventsOutput(
                status=SearchStatus.NO_RESULTS,
                total_hits=0,
                error_message=None,
                events=[],
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
