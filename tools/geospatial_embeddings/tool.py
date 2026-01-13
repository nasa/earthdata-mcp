"""
Geospatial Embeddings Tool

This module provides functionality to convert natural language location queries
into geometric representations (like polygons or points) for use in geospatial
applications. It includes Redis-based caching to improve performance and
Langfuse integration for observability.
"""

import hashlib

from typing import Any, Dict
import redis
from langfuse import observe, get_client

from util.natural_language_geocoder import convert_text_to_geom
from util.redis_client import CacheClient
from tools.geospatial_embeddings.output_model import GeospatialOutput

# Initialize clients
langfuse = get_client()
cache = CacheClient()


def get_cache_key(location: str) -> str:
    """Generate a consistent cache key for the location."""
    normalized = location.lower().strip()
    return f"geocode:{hashlib.md5(normalized.encode()).hexdigest()}"


@observe(name="cache_lookup")
def get_from_cache(location: str) -> Dict[str, Any]:
    """Get geocoded result from Redis cache."""
    try:
        cache_key = get_cache_key(location)

        return cache.get(cache_key)

    except redis.RedisError as e:
        print(f"Redis error when reading from cache: {e}")
        return None


@observe(name="cache_store")
def store_in_cache(location: str, result: Dict[str, Any], ttl: int = 900) -> None:
    """Store geocoded result in Redis cache."""
    try:
        cache_key = get_cache_key(location)
        return cache.set(cache_key, result, ttl)
    except redis.RedisError as e:
        print(f"Redis error when storing to cache: {e}")


@observe(name="natural_language_geocode")
def natural_language_geocode(location: str) -> GeospatialOutput:
    """Convert natural language location query to geometry with caching.
    Args:
        location: A natural language description of a geographic location.
                Can include various formats and specificity levels:

                **Supported Location Types:**
                - Cities: "San Francisco", "New York City", "London"
                - Regions: "San Francisco Bay Area", "Silicon Valley", "New England"
                - States/Provinces: "California", "Texas", "Ontario, Canada"
                - Countries: "United States", "Brazil", "Japan"
                - Geographic features: "Pacific Ocean", "Rocky Mountains", "Amazon Basin"
                - Administrative areas: "San Francisco County", "King County, Washington"
                - Landmarks: "Golden Gate Bridge area", "Central Park vicinity"
                - Descriptive locations: "Northern California coast", "Eastern seaboard"

                **Format Guidelines:**
                - Use common, recognizable place names
                - Include context for disambiguation (e.g., "Paris, France" vs "Paris, Texas")
                - Avoid overly specific addresses or coordinates
                - Natural language is preferred over formal geographic codes
                - Both singular locations and regions are supported

                **Examples:**
                - ✅ "San Francisco Bay Area" → Returns polygon covering SF Bay region
                - ✅ "Downtown Seattle" → Returns polygon of Seattle's downtown area
                - ✅ "California Central Valley" → Returns polygon of agricultural region
                - ✅ "Mediterranean Sea" → Returns polygon covering sea area
                - ⚠️  "123 Main St, Anytown USA" → May not geocode well (too specific)
    """

    if not location:
        langfuse.update_current_trace(
            tags=["error", "empty_location"],
            metadata={"error_type": "empty_location", "location_length": 0},
        )
        return GeospatialOutput(
            error="No location query provided. Please specify a location.",
            success=False,
        )

    # Check cache first
    cached_result = get_from_cache(location)
    if cached_result:
        cached_result["from_cache"] = True
        langfuse.update_current_trace(
            tags=["cache_hit", "success"],
            metadata={
                "cache_hit": True,
                "cache_key": get_cache_key(location),
                "location_length": len(location),
            },
        )
        return GeospatialOutput(**cached_result)

    # Cache miss - geocode the location
    try:
        geom = convert_text_to_geom(location)

        if geom is not None:
            result = {
                "geoLocation": location,
                "geometry": str(geom),
                "success": True,
                "from_cache": False,
            }

            # Store in cache
            store_in_cache(location, result)

            langfuse.update_current_trace(
                tags=["cache_miss", "success", "geocoded"],
                metadata={
                    "cache_hit": False,
                    "success": True,
                    "geometry_type": type(geom).__name__,
                    "location_length": len(location),
                },
            )

            return GeospatialOutput(**result)

        langfuse.update_current_trace(
            tags=["cache_miss", "error", "geocoding_failed"],
            metadata={
                "error_type": "geocoding_failed",
                "success": False,
                "location_length": len(location),
            },
        )

        return GeospatialOutput(
            error=f"Unable to geocode the location '{location}'.",
            success=False,
            from_cache=False,
        )

    except (ValueError, TypeError) as e:
        langfuse.update_current_trace(
            tags=["cache_miss", "error", "validation_error"],
            metadata={
                "error_type": "validation_error",
                "location_length": len(location),
            },
        )
        return GeospatialOutput(
            error=f"Invalid location format: {str(e)}",
            success=False,
        )

    except Exception as e:
        langfuse.update_current_trace(
            tags=["cache_miss", "error", "exception"],
            metadata={
                "error_type": "exception",
                "exception_class": type(e).__name__,
                "success": False,
                "location_length": len(location),
            },
        )
        return GeospatialOutput(
            error=f"Unexpected error: {str(e)}",
            success=False,
        )
