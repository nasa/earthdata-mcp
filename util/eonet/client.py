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

class WKTError(Exception):
    """Raised when EONET client can't convert geometry to WKT for CMR"""


def _is_valid_poly_coord(coords: list):
    """
    Make sure the coordinate lists stored in the 'geometry' > 'coordinates' list field
    of a GeoJSON result follow this format: '[float float]'.

    Args:
        geo_type: The GeoJSON object type.
        coords: The coordinates of the GeoJSON object.

    Returns:
        The WKT string representation of the GeoJSON object.

    Raises:
        EONETError: If the EONET client can't convert the GeoJSON object to WKT format.
    """
    if len(coords) == 2:
        if (type(coords[0]) == float) and (type(coords[1]) == float):
            return True
    return False


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


def convert_to_wkt(geo_type: str, coords: list) -> str:
    """
    Converts GeoJSON geometry to WKT geometry format.

    Args:
        geo_type: The GeoJSON object type.
        coords: The coordinates of the GeoJSON object.

    Returns:
        The WKT string representation of the GeoJSON object.

    Raises:
        EONETError: If the EONET client can't convert the GeoJSON object to WKT format.
    """
    try:
        if (type(geo_type) != str) or (type(coords) != list) or (type(coords) != list[list]):
            raise WKTError(
                f"Could not convert to WKT. Received incorrect input type: geo_type: {type(geo_type)}, coords: {type(coords)}"
            )
        else:
            if geo_type == "Point":
                if len(coords) != 2:
                    raise WKTError(f"Could not convert to WKT. Incorrect number of coordinate values for 'Point' type: {len(coords)}")
                elif (type(coords[0]) != float) or (type(coords[1]) != float):
                    raise WKTError(f"Could not convert to WKT. Attempted to create 'Point' type from invalid data types: [{type(coords[0])} {type(coords[1])}]")
                else:
                    return f"POINT({coords[0]} {coords[1]})" 
            elif geo_type == "Polygon":
                if (coords[0] != coords[-1]) or (len(coords) < 4):
                    raise WKTError(f"Could not convert to WKT. A closed 'Polygon' type cannot be created from the following coordinates: {coords}")
                else:
                    poly_str = "POLYGON(("
                    for point in coords:
                        if _is_valid_poly_coord(point):
                            poly_str = poly_str + f"{point[0]} {point[1]}, "
                        else:
                            raise WKTError(f"Could not convert to WKT. Invalid polygon point format: {point}")
                    return poly_str[:-2] + "))" 
            else:
                raise WKTError(f"Could not convert to WKT. Unsupported GeoJSON object type: {geo_type}")
    except WKTError as e:
        raise EONETError(f"The given GeoJSON geometry could not be converted to WKT: {e}") from e

