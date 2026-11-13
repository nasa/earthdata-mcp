"""Query EONET for natural events."""

import logging

from fastmcp.exceptions import ToolError
from langfuse import observe

from models.tools.cmr_search import SearchStatus
from models.tools.get_events import (
    CATEGORIES_TYPE,
    STATUS_TYPE,
    GetEventsInput,
    GetEventsOutput,
)
from util.eonet.client import (
    EONETError,
    events,
)
from util.langfuse import trace_update

logger = logging.getLogger(__name__)


def _build_response(results: dict) -> dict:
    """Builds the tool response using the fetched EONET data."""
    try:
        if ("features" in results) and ("type" in results):
            if len(results["features"]) == 0:
                return GetEventsOutput(
                    status=SearchStatus.NO_RESULTS,
                    error_message=None,
                    data={},
                ).model_dump()
            return GetEventsOutput(
                status=SearchStatus.SUCCESS,
                error_message=None,
                data=results,
            ).model_dump()
        raise EONETError("Unexpected response shape: 'features' and/or 'type' keys missing.")
    except (ValueError, TypeError, EONETError) as e:
        logger.error("Results could not be saved: %s", e)
        raise ToolError(f"Attempting to save malformed results: {str(e)}") from e


@observe(name="get_events")
def get_events(  # pylint: disable=too-many-arguments
    source: str | None = None,
    category: CATEGORIES_TYPE | None = None,
    status: STATUS_TYPE = "all",
    limit: int = 5,
    days: int | None = None,
    start: str | None = None,
    end: str | None = None,
    magID: str | None = None,
    magMin: float | None = None,
    magMax: float | None = None,
    bbox: str | None = None,
) -> dict:
    """Send a request to the EONET API to retrieve event data based on specified parameters.

    This tool takes an EONET API endpoint name (events or events/geojson) and a list of parameters,
    sending a request to the specified endpoint with the given parameters. It returns the results
    formatted to contain the data itself and labels describing the data.
    """
    trace_update(
        tags=["eonet", "eventsapi"],
        metadata={
            "source": source,
            "category": category,
            "status": status,
            "limit": limit,
            "days": days,
            "start": start,
            "end": end,
            "magID": magID,
            "magMin": magMin,
            "magMax": magMax,
            "bbox": bbox,
        },
    )

    try:
        params = GetEventsInput(
            source=source,
            category=category,
            status=status,
            limit=limit,
            days=days,
            start=start,
            end=end,
            magID=magID,
            magMin=magMin,
            magMax=magMax,
            bbox=bbox,
        )
    except (ValueError, TypeError) as e:
        logger.warning("get_events input validation failed: %s", e)
        raise ToolError(f"get_events {type(e).__name__}: {str(e)}") from e

    try:
        results = events(
            params.model_dump(), True
        )  # Automatically use GeoJSON endpoint (normal events endpoint still available)
    except EONETError as e:
        logger.error("EONET API request failed: %s", e)
        raise ToolError(f"Could not retrieve results from EONET: {str(e)}") from e

    return _build_response(results)
