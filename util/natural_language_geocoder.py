"""
Natural Language Geocoder Module

https://github.com/Element84/natural-language-geocoding
https://github.com/Element84/e84-geoai-common
"""

import os
import json

from shapely.geometry import shape, mapping
from shapely.ops import orient

from e84_geoai_common.llm.models.nova import BedrockNovaLLM
from e84_geoai_common.geometry import geometry_to_geojson
from e84_geoai_common.geometry import simplify_geometry


# TEMPORARY SOLUTION: Monkey-patch for Lambda compatibility
# This monkey-patch is needed because the current version of the natural_language_geocoding library
# uses "./temp" as the default cache directory, which is not writable in AWS Lambda environments.
# We override the default to use "/tmp", which is the writable directory in Lambda.
#
# Remove this monkey-patch once the library is updated to handle Lambda environments.
# Issue: [https://github.com/Element84/natural-language-geocoding/issues/15]
import natural_language_geocoding.geocode_index.hierachical_place_cache as hpc

from natural_language_geocoding import extract_geometry_from_text
from natural_language_geocoding.geocode_index.geocode_index_place_lookup import (
    GeocodeIndexPlaceLookup,
)

_original_init = hpc.PlaceCache.__init__


def lambda_safe_init(self, *args, **kwargs):
    """
    Lambda-safe initialization wrapper for PlaceCache.__init__.

    This function replaces the original PlaceCache.__init__ method to ensure
    compatibility with AWS Lambda environments. The original implementation
    uses "./temp" as the default cache directory, which is not writable in
    Lambda. This wrapper redirects cache operations to "/tmp", which is the
    writable directory in Lambda environments.
    """
    if "cache_dir" not in kwargs or kwargs["cache_dir"] == "./temp":
        kwargs["cache_dir"] = "/tmp"
    return _original_init(self, *args, **kwargs)


hpc.PlaceCache.__init__ = lambda_safe_init


simplify_geom_max_point = int(os.getenv("SIMPLIFY_GEOM_MAX_POINT", "1000"))


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

        simplified_geom = simplify_geometry(
            geom=geometry, max_points=simplify_geom_max_point
        )
        return simplified_geom
    except Exception as e:
        print(f"Error in natural_language_geocoder: {str(e)}")
        return None


def fix_geometry(geom):
    """
    Fix the orientation of a geometry to ensure polygons are counter-clockwise.

    This function takes a GeoJSON geometry and ensures that:
    - Polygons are oriented counter-clockwise
    - MultiPolygons have all their constituent polygons oriented counter-clockwise
    - Other geometry types are left unchanged

    Args:
        geom (dict): A GeoJSON geometry object

    Returns:
        dict: The input geometry with polygons oriented counter-clockwise

    Note:
        This function uses the Shapely library to perform the orientation fix.
    """
    if geom["type"] == "Polygon":
        # Convert to shapely geometry, orient it counter-clockwise, and convert back to GeoJSON
        shp = shape(geom)
        oriented = orient(shp, sign=1.0)  # 1.0 for counter-clockwise
        return mapping(oriented)

    if geom["type"] == "MultiPolygon":
        # Fix each polygon in the MultiPolygon
        fixed_polys = [
            fix_geometry({"type": "Polygon", "coordinates": poly})
            for poly in geom["coordinates"]
        ]
        return {
            "type": "MultiPolygon",
            "coordinates": [p["coordinates"] for p in fixed_polys],
        }

    # Return other geometries unchanged
    return geom


def convert_geometry_to_geojson(geometry):
    """
    Convert a geometry object to GeoJSON format.

    Args:
        geometry: The geometry object to convert.

    Returns:
        dict: GeoJSON representation of the geometry.

    Raises:
        ValueError: If the geometry is invalid or cannot be parsed.
    """
    try:
        geojson_geometry = geometry_to_geojson(geometry)
        geojson = json.loads(geojson_geometry)

        # Apply the fix to the geometry
        if geojson["type"] == "FeatureCollection":
            for feature in geojson["features"]:
                feature["geometry"] = fix_geometry(feature["geometry"])
        elif geojson["type"] == "Feature":
            geojson["geometry"] = fix_geometry(geojson["geometry"])
        else:
            geojson = fix_geometry(geojson)

        return geojson
    except (AttributeError, json.JSONDecodeError, ValueError) as e:
        raise ValueError(f"Failed to convert geometry to GeoJSON: {str(e)}") from e
