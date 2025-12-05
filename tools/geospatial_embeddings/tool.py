from typing import Any

from util.natural_language_geocoder import convert_text_to_geom


def natural_language_geocode(location: str) -> dict[str, Any]:
    """Convert natural language location query to geometry.

    Args:
        location: A natural language location query (e.g., "San Francisco Bay Area")

    Returns:
        Dictionary with geometry information or error message
    """

    return {"result": "NOT IMPLEMENTED YET"}
    if not location:
        return {"error": "No location query provided. Please specify a location."}

    geom = convert_text_to_geom(location)

    if geom is not None:
        return {"geoLocation": location, "geometry": str(geom), "success": True}
    else:
        return {
            "error": f"""Unable to geocode the location '{location}'.
                  The location might be too vague, not recognized,
                  or there was an error in the geocoding process.""",
            "success": False,
        }
