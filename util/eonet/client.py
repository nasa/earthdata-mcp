"""NASA EONET (Earth Observatory Natural Event Tracker) API client."""

import logging

import requests

logger = logging.getLogger(__name__)

EONET_BASE_URL = "https://eonet.gsfc.nasa.gov/api"


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
    if is_geojson:
        url = f"{EONET_BASE_URL}/v3/events/geojson"
    else:
        url = f"{EONET_BASE_URL}/v3/events"
    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    results = response.json()

    if len(results["events"]) == 0:
        return {}

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
    url = f"{EONET_BASE_URL}/v3/categories/{category}"
    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    results = response.json()

    if len(results["events"]) == 0:
        return {}

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
    url = f"{EONET_BASE_URL}/v3/layers/{category_id}"
    response = requests.get(url, params={}, timeout=10)
    response.raise_for_status()
    results = response.json()

    non_empty_layers = []

    # Filter out all empty layers lists from the results
    for layer in results["categories"]:
        if layer["layers"] != "":
            non_empty_layers.append(layer)

    if len(non_empty_layers) == 0:
        return {}

    return results
