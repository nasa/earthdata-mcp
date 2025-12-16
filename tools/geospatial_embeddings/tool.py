import json
import hashlib
from typing import Any, Dict, Optional
import redis
import os
from langfuse import observe, get_client

from util.natural_language_geocoder import convert_text_to_geom

# Initialize Langfuse client
langfuse = get_client()

redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    password=os.getenv("REDIS_PASSWORD"),
    ssl="true",
    ssl_cert_reqs=None,
)


def get_cache_key(location: str) -> str:
    """Generate a consistent cache key for the location."""
    normalized = location.lower().strip()
    return f"geocode:{hashlib.md5(normalized.encode()).hexdigest()}"


@observe(name="cache_lookup")
def get_from_cache(location: str) -> Optional[Dict[str, Any]]:
    """Get geocoded result from Redis cache."""
    try:
        cache_key = get_cache_key(location)
        cached_result = redis_client.get(cache_key)

        if cached_result:
            return json.loads(cached_result)
        return None
    except Exception as e:
        print(f"Cache read error: {e}")
        return None


@observe(name="cache_store")
def store_in_cache(location: str, result: Dict[str, Any], ttl: int = 900) -> None:
    """Store geocoded result in Redis cache."""
    try:
        cache_key = get_cache_key(location)
        redis_client.setex(cache_key, ttl, json.dumps(result))
    except Exception as e:
        print(f"Cache write error: {e}")


@observe(name="natural_language_geocode")
def natural_language_geocode(location: str) -> Dict[str, Any]:
    """Convert natural language location query to geometry.

    Args:
        location: A natural language location query (e.g., "San Francisco Bay Area")

    Returns:
        Dictionary with geometry information or error message
    """

    if not location:
        result = {
            "error": "No location query provided. Please specify a location.",
            "success": False,
        }
        langfuse.update_current_trace(
            tags=["error", "empty_location"],
            metadata={"error_type": "empty_location", "location_length": 0},
        )
        return result

    # Check cache first
    cached_result = get_from_cache(location)

    if cached_result:
        # Cache hit
        cached_result["from_cache"] = True
        langfuse.update_current_trace(
            tags=["cache_hit", "success"],
            metadata={
                "cache_hit": True,
                "cache_key": get_cache_key(location),
                "location_length": len(location),
            },
        )
        return cached_result

    # Cache miss - need to geocode
    try:
        geom = convert_text_to_geom(location)

        if geom is not None:
            result = {"geoLocation": location, "geometry": str(geom), "success": True}

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

            return result
        else:
            result = {
                "error": f"Unable to geocode the location '{location}'. "
                f"The location might be too vague, not recognized, "
                f"or there was an error in the geocoding process.",
                "success": False,
            }

            langfuse.update_current_trace(
                tags=["cache_miss", "error", "geocoding_failed"],
                metadata={
                    "error_type": "geocoding_failed",
                    "success": False,
                    "location_length": len(location),
                },
            )

            return result

    except Exception as e:
        result = {"error": f"Exception during geocoding: {str(e)}", "success": False}

        langfuse.update_current_trace(
            tags=["cache_miss", "error", "exception"],
            metadata={
                "error_type": "exception",
                "exception_class": type(e).__name__,
                "success": False,
                "location_length": len(location),
            },
        )

        return result
