"""
Spatial constraint extraction with LLM parsing, geocoding, and caching.
"""

# pylint: disable=duplicate-code  # Intentional code patterns shared with extract_temporal_constraint.py

import logging
from datetime import UTC, datetime

import instructor
from langfuse import observe

from tools.discover_data.models.extraction import (
    ParsedSpatialExtraction,
)
from tools.discover_data.utils.llm_extraction import MODEL_ID, PROVIDER, load_extraction_prompt
from tools.models.constraints import SpatialConstraint
from util.cache import get_cache_client
from util.langfuse import trace_update
from util.natural_language_geocoder import convert_text_to_geom

logger = logging.getLogger(__name__)

try:
    cache = get_cache_client()
except Exception as e:
    logger.warning("Failed to initialize cache client: %s", e)
    cache = None


@observe(name="extract_spatial_with_llm")
def extract_spatial_with_llm(query: str) -> ParsedSpatialExtraction | None:
    """LLM-based spatial extraction.

    Args:
        query: Natural language description potentially containing spatial info.

    Returns:
        ParsedSpatialExtraction (location name, contextual phrase, reasoning, cache key),
        or None when no spatial signal is found; raises on LLM setup/errors.
    """
    try:
        client = instructor.from_provider(f"{PROVIDER}/{MODEL_ID}")
    except Exception as e:
        trace_update(
            tags=["error", "client_init_error"],
            metadata={"error_type": "client_init_error", "message": str(e), "success": False},
        )
        raise RuntimeError(
            f"Failed to initialize instructor client with provider '{PROVIDER}' and model '{MODEL_ID}': {e}"
        ) from e

    today = datetime.now(UTC).strftime("%Y-%m-%d")
    system_prompt = load_extraction_prompt("spatial_extraction.md", today)

    try:
        output = client.create(
            modelId=MODEL_ID,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query},
            ],
            response_model=ParsedSpatialExtraction,
        )

        if not output.location_name and not output.location_with_context:
            logger.debug("LLM returned no spatial information for query: %s", query)
            return None

        # Capitalize location names properly while preserving acronyms
        # Only capitalize first letter, preserve acronyms and lowercase prepositions
        def capitalize_location(location: str) -> str:
            """Capitalize location name: first letter capitalized, preserve acronyms."""
            if not location:
                return location
            # Capitalize first letter, keep rest as-is (preserves "of", "USA", etc.)
            return location[0].upper() + location[1:] if len(location) > 1 else location.upper()

        location_name = capitalize_location(output.location_name) if output.location_name else None
        location_with_context = (
            capitalize_location(output.location_with_context)
            if output.location_with_context
            else None
        )

        logger.debug(
            "LLM extracted location: %s (canonical: %s)",
            location_with_context,
            location_name,
        )

        return ParsedSpatialExtraction(
            location_name=location_name,
            location_with_context=location_with_context,
            reasoning=output.reasoning,
        )
    except Exception as e:
        trace_update(
            tags=["error", "llm_error"],
            metadata={"error_type": "llm_error", "message": str(e), "success": False},
        )
        raise RuntimeError(f"Failed to extract spatial info from query '{query}': {e}") from e


@observe(name="extract_spatial_constraint")
def extract_spatial_constraint(query: str) -> SpatialConstraint:  # pylint: disable=too-many-branches,too-many-return-statements
    """Convert natural language location query to spatial constraint with caching.

    Args:
        query: A natural language description of a geographic location.
                 Can include cities, regions, countries, geographic features, etc.

    Returns:
        SpatialConstraint with location query and WKT geometry (if successful)
    """
    if not query:
        logger.warning("Empty query provided for spatial constraint extraction.")
        return SpatialConstraint(
            location=None,
            wkt_geometry=None,
        )

    # Use LLM to extract spatial info from the query
    extraction = extract_spatial_with_llm(query)
    if not extraction or not extraction.location_with_context:
        logger.debug("No spatial information extracted from query: %s", query)
        return SpatialConstraint(
            location=None,
            wkt_geometry=None,
            reasoning="No spatial information found in query",
        )

    location_to_geocode = extraction.location_with_context
    canonical_name = extraction.location_name

    # Check cache using standardized location name
    if cache and canonical_name:
        try:
            cache_key = extraction.cache_key
            cached_geom = cache.get(cache_key)
            if cached_geom:
                trace_update(
                    tags=["cache_hit", "success"],
                    metadata={"cache_hit": True, "canonical_name": canonical_name},
                )
                logger.debug("Cache hit for location: %s (key: %s)", canonical_name, cache_key)
                return SpatialConstraint(
                    location=location_to_geocode,
                    wkt_geometry=cached_geom,
                    reasoning=f"{extraction.reasoning} (cached)",
                )
        except Exception as e:
            logger.debug("Cache lookup failed: %s", e)

    # Cache miss or cache disabled - geocode the location
    try:
        geom = convert_text_to_geom(location_to_geocode)

        if geom is None:
            logger.warning(
                "Failed to geocode location: %s (check Redis/OpenSearch connectivity)",
                location_to_geocode,
            )
            trace_update(
                tags=["cache_miss", "error", "geocoding_failed"],
                metadata={"error_type": "geocoding_failed", "success": False},
            )
            return SpatialConstraint(
                location=location_to_geocode,
                wkt_geometry=None,
                reasoning=extraction.reasoning,
            )

        # Store in cache
        if cache and canonical_name:
            try:
                cache_key = extraction.cache_key
                cache.set(cache_key, geom, ttl=900)
            except Exception as e:
                logger.debug("Cache store failed: %s", e)

        trace_update(
            tags=["cache_miss", "success", "geocoded"],
            metadata={
                "cache_hit": False,
                "success": True,
            },
        )

        logger.debug(
            "Successfully geocoded location '%s': length=%d chars",
            canonical_name,
            len(geom),
        )
        return SpatialConstraint(
            location=location_to_geocode,
            wkt_geometry=geom,
            reasoning=extraction.reasoning,
        )

    except (ValueError, TypeError) as e:
        logger.warning("Invalid location format for '%s': %s", location_to_geocode, e)
        trace_update(
            tags=["error", "validation_error"],
            metadata={"error_type": "validation_error"},
        )
        return SpatialConstraint(
            location=location_to_geocode,
            wkt_geometry=None,
            reasoning=extraction.reasoning,
        )

    except Exception as e:
        logger.exception("Unexpected error geocoding '%s'", location_to_geocode)
        trace_update(
            tags=["error", "exception"],
            metadata={
                "error_type": "exception",
                "exception_class": type(e).__name__,
            },
        )
        return SpatialConstraint(
            location=location_to_geocode,
            wkt_geometry=None,
            reasoning=extraction.reasoning,
        )
