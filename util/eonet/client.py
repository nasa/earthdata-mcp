"""NASA EONET (Earth Observatory Natural Event Tracker) API client."""

import logging

import requests

from util.environment import get_client_id

logger = logging.getLogger(__name__)

EONET_BASE_URL = "https://eonet.gsfc.nasa.gov/api/v3"
CLIENT_ID = get_client_id()
request_url = ""

class EONETError(Exception):
    """Raised when an EONET API request fails."""

def events(params: dict | None = None, is_geojson: bool = False) -> dict:
    """
    Search across all current NRT natural events.

    This performs a direct call to the EONET API. It returns results from the event
    endpoint.

    Args:
        params: Optional dictionary of query parameters to filter events.
        is_geojson: Optional boolean to specify if the GeoJSON endpoint should be used
        instead. Default is false.

    Returns:
        JSON object containing a list of returned events. Returns empty object if
        no events are found.

    Raises:
        requests.RequestException: If the EONET API events endpoint request fails.
    """
    global request_url

    url = f"{EONET_BASE_URL}/events/geojson" if is_geojson else f"{EONET_BASE_URL}/events"
    request_url = url

    try:
        response = requests.get(url, params=params, headers={"Client-Id": CLIENT_ID}, timeout=10)
        response.raise_for_status()
        results = response.json()
    except requests.RequestException as e:
        raise EONETError(f"Failed to fetch events from EONET: {e}") from e
    except ValueError as e:
        raise EONETError(f"Non-JSON response for event request with params '{list(params)}'") from e

    if not is_geojson:
        if not isinstance(results, dict) or "events" not in results:
            raise EONETError(f"Unexpected response shape for events request. Response keys: {list(results.keys())}")
    else:
        if not isinstance(results, dict) or "features" not in results:
            raise EONETError(f"Unexpected response shape for geojson events request. Response keys: {list(results.keys())}")

    return results
