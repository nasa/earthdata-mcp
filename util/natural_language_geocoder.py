"""
Natural Language Geocoder Module

https://github.com/Element84/natural-language-geocoding
https://github.com/Element84/e84-geoai-common
"""

import logging
import os

from e84_geoai_common.geometry import simplify_geometry
from e84_geoai_common.llm.models.nova import BedrockNovaLLM
from langfuse import observe
from natural_language_geocoding import extract_geometry_from_text
from natural_language_geocoding.geocode_index.geocode_index_place_lookup import (
    GeocodeIndexPlaceLookup,
)
from shapely import make_valid, orient_polygons

logger = logging.getLogger(__name__)

SIMPLIFY_GEOM_MAX_POINT = int(os.getenv("SIMPLIFY_GEOM_MAX_POINT", "4900"))


@observe(name="convert_text_to_geom")
def convert_text_to_geom(location_query: str) -> str:
    """
    Convert a natural language location query into a geometric representation using OpenSearch.

    This function uses a combination of AWS Bedrock's Nova LLM and OpenSearch to interpret
    natural language location descriptions and convert them into geometric representations.

    Args:
        location_query (str): A natural language description of a location.

    Returns:
        str: A geometric representation of the location in WKT format.
            Returns None if an error occurs during the conversion process.
    """
    try:
        # Initialize BedrockNovaLLM
        bedrock_llm = BedrockNovaLLM()

        # Geocode text description to geometry
        geometry = extract_geometry_from_text(
            bedrock_llm, location_query, GeocodeIndexPlaceLookup()
        )

        # Log geometry details for debugging
        try:
            geom_info = {"type": geometry.geom_type, "bounds": geometry.bounds}

            if geometry.geom_type in ("Point",):
                geom_info["num_coords"] = 1
            elif geometry.geom_type in ("LineString", "LinearRing"):
                geom_info["num_coords"] = len(geometry.coords)
            elif geometry.geom_type == "Polygon":
                geom_info["num_coords"] = len(geometry.exterior.coords)
            elif geometry.geom_type.startswith("Multi"):
                geom_info["num_parts"] = len(geometry.geoms)

            logger.debug(
                "Extracted geometry for '%s': %s",
                location_query,
                geom_info,
            )
        except Exception as e:
            logger.debug("Unable to inspect extracted geometry: %s", e)

        # Initial simplification to reduce vertex count
        simplified_geom = simplify_geometry(geom=geometry, max_points=SIMPLIFY_GEOM_MAX_POINT)

        # Convert to WKT and validate the geometry is usable
        wkt_result = _normalize_geometry_to_wkt(simplified_geom)

        return wkt_result
    except Exception as e:
        logger.warning(
            "Error geocoding location '%s': %s (%s)",
            location_query,
            str(e),
            type(e).__name__,
        )
        logger.debug("Full traceback:", exc_info=True)
        return None


def _normalize_geometry_to_wkt(geometry) -> str | None:
    """
    Convert Shapely geometry to WKT format for spatial queries.

    The geocoder and simplify_geometry both return Shapely BaseGeometry objects.
    This converts them to WKT strings with normalized formatting for database and CMR queries.

    Args:
        geometry: Shapely geometry object (Point, Polygon, MultiPolygon, etc.)

    Returns:
        WKT string with normalized formatting, or None if input is None

    Raises:
        ValueError: If geometry is invalid or not a Shapely object
    """
    if geometry is None:
        return None

    # Validate it's a Shapely geometry object
    if not hasattr(geometry, "geom_type"):
        raise ValueError("Expected Shapely geometry object")

    # Repair invalid geometries using make_valid()
    # This fixes self-intersections, duplicate vertices, and topology issues
    if not geometry.is_valid:
        logger.warning("Invalid geometry detected, attempting to fix with make_valid()")
        try:
            geometry = make_valid(geometry)
        except Exception as e:
            raise ValueError(f"Invalid geometry: {e}") from e

        if geometry.is_empty:
            raise ValueError("Geometry is empty after make_valid() repair")
        if not geometry.is_valid:
            raise ValueError("Geometry is invalid and could not be repaired")

    if geometry.geom_type in ("Polygon", "MultiPolygon"):
        # Forces CCW exterior rings and CW interior rings for CMR
        geometry = orient_polygons(geometry)

    # Convert to WKT
    return geometry.wkt
