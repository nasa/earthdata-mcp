"""
Natural Language Geocoder Module

https://github.com/Element84/natural-language-geocoding
https://github.com/Element84/e84-geoai-common
"""

import logging

from e84_geoai_common.geometry import simplify_geometry
from e84_geoai_common.llm.models.nova import BedrockNovaLLM
from natural_language_geocoding import extract_geometry_from_text
from natural_language_geocoding.geocode_index.geocode_index_place_lookup import (
    GeocodeIndexPlaceLookup,
)
from pydantic import ValidationError as PydanticValidationError

from util.geocoder_exceptions import ValidationError

logger = logging.getLogger(__name__)

SIMPLIFY_GEOM_MAX_POINT = 1000


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

        # If still too complex, apply more aggressive simplification
        # Using 50k chars as a threshold (roughly 500+ vertices)
        if wkt_result and len(wkt_result) > 50000:
            logger.warning(
                "Geometry for '%s' is very complex (%d chars), attempting aggressive simplification",
                location_query,
                len(wkt_result),
            )
            simplified_geom = simplify_geometry(geom=geometry, max_points=100)
            wkt_result = _normalize_geometry_to_wkt(simplified_geom)

        return wkt_result
    except PydanticValidationError as e:
        logger.debug("Geocoder output validation failed for '%s': %s", location_query, e)
        raise ValidationError("Geocoder output validation failed") from e
    except ValidationError:
        raise
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
    This converts them to WKT strings with normalized formatting for database queries.

    Args:
        geometry: Shapely geometry object (Point, Polygon, MultiPolygon, etc.)

    Returns:
        WKT string with normalized formatting, or None if input is None

    Raises:
        ValidationError: If geometry is invalid or not a Shapely object
    """
    if geometry is None:
        return None

    # Validate it's a Shapely geometry object
    if not hasattr(geometry, "geom_type"):
        raise ValidationError("Expected Shapely geometry object")

    # Repair invalid geometries using buffer(0)
    # This fixes self-intersections, duplicate vertices, and topology issues
    if not geometry.is_valid:
        logger.warning("Invalid geometry detected, attempting to fix with buffer(0)")
        try:
            geometry = geometry.buffer(0)
            if geometry.is_empty:
                raise ValidationError("Geometry is empty after buffer(0) repair")
            if not geometry.is_valid:
                raise ValidationError("Geometry is invalid and could not be repaired")
        except Exception as e:
            raise ValidationError(f"Invalid geometry: {e}") from e

    # Convert to WKT and normalize formatting
    # Shapely outputs "POLYGON ((..." but some parsers require "POLYGON((...""
    wkt_str = geometry.wkt
    wkt_str = wkt_str.replace("POLYGON (", "POLYGON(")
    wkt_str = wkt_str.replace("MULTIPOLYGON (", "MULTIPOLYGON(")
    wkt_str = wkt_str.replace("LINESTRING (", "LINESTRING(")
    wkt_str = wkt_str.replace("MULTILINESTRING (", "MULTILINESTRING(")
    wkt_str = wkt_str.replace("POINT (", "POINT(")
    wkt_str = wkt_str.replace("MULTIPOINT (", "MULTIPOINT(")

    return wkt_str
