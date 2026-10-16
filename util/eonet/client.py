"""NASA EONET (Earth Observatory Natural Event Tracker) API client."""

import logging

import requests

from util.environment import get_client_id

logger = logging.getLogger(__name__)

EONET_BASE_URL = "https://eonet.gsfc.nasa.gov/api/v3"
CLIENT_ID = get_client_id()

class EONETError(Exception):
    """Raised when an EONET API request fails."""

def events(params: dict | None = None, is_geojson: bool = False) -> dict:
    """
    Search across all current NRT natural events.

    This performs a direct call to the EONET API. It returns results from the event
    endpoint.

    Args:
        params: Optional dictionary of query parameters to filter events.
        is_geojson: Optional boolean to specify if the GeoJSON endpint should be used
        instead. Default is false.

    Returns:
        JSON object containing a list of returned events. Returns empty object if
        no events are found.

    Raises:
        requests.RequestException: If the EONET API events endpoint request fails.
    """
    url = f"{EONET_BASE_URL}/events/geojson" if is_geojson else f"{EONET_BASE_URL}/events"

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


def categories(category: str, params: dict | None = None) -> dict:
    """
    Search by category for events.

    This performs a direct call to the EONET API. It returns results from the category
    endpoint.

    Args:
        category: The category to search within (e.g., 'wildfires').
        params: Optional dictionary of query parameters to filter events.

    Returns:
        JSON object containing a list of returned events. Returns empty object if
        no events are found.

    Raises:
        requests.RequestException: If the EONET API category endpoint request fails.
    """
    url = f"{EONET_BASE_URL}/categories/{category}" if category else f"{EONET_BASE_URL}/categories"

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        results = response.json()
    except requests.RequestException as e:
        raise EONETError(f"Failed to fetch events for category '{category}', or all categories, from EONET: {e}") from e

    if category:
        if not isinstance(results, dict) or "events" not in results:
            raise EONETError(f"Unexpected response shape for cateogory '{category}'. Response keys: {list(results.keys())}")
    else:
        if not isinstance(results, dict) or "categories" not in results:
            raise EONETError(f"Unexpected response shape for category endpoint. Response keys: {list(results.keys())}")

    return results


def layers(category_id: str) -> dict:
    """
    Search across all event layers.

    This performs a direct call to the EONET API. It returns results from the layer
    endpoint.

    Args:
        category_id: The ID of the category to search within (e.g., 'wildfires').

    Returns:
        JSON object containing a list of returned layers for the specified categor(ies).
        Returns empty object if no layers are found.

    Raises:
        requests.RequestException: If the EONET API layers endpoint request fails.
    """
    url = f"{EONET_BASE_URL}/layers/{category_id}"

    try:
        response = requests.get(url, params={}, timeout=10)
        response.raise_for_status()
        results = response.json()
    except requests.RequestException as e:
        raise EONETError(f"Failed to fetch layers for category '{category_id}' from EONET: {e}") from e

    if not isinstance(results, dict) or "categories" not in results:
        raise EONETError(f"Unexpected layers response shape for category '{category_id}'. Response keys: {list(results.keys())}")

    return results
