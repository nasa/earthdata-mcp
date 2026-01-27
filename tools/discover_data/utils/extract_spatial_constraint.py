"""
LLM-based spatial constraint extraction with geocoding and caching.

Two-layer design:
  - _extract_spatial_with_llm: Pure LLM parsing → SpatialExtractionResult
  - extract_spatial_constraint_from_query: Wrapper that geocodes location + caches WKT

Cache keys use canonical location names from the LLM to ensure "Paris",
"Paris, France", and "within 100km of Paris" all hit the same cache entry.
(Note: This depends on LLM consistency; future work could use geocoder output
as the canonical key for stronger normalization.)
"""

import hashlib
import logging
from datetime import UTC, datetime
from pathlib import Path

import instructor
import redis
from langfuse import get_client, observe

from tools.discover_data.input_model import SpatialConstraint
from util.cache import get_cache_client
from util.natural_language_geocoder import convert_text_to_geom

logger = logging.getLogger(__name__)

try:
    LANGFUSE = get_client()
except Exception as e:
    logger.warning("Failed to initialize Langfuse client: %s", e)
    LANGFUSE = None

try:
    cache = get_cache_client()
except Exception as e:
    logger.warning("Failed to initialize cache client: %s", e)
    cache = None


class SpatialExtractionResult:
    """Result of LLM-based spatial extraction."""

    def __init__(self, location_name: str | None, location_with_context: str | None, reasoning: str | None):
        self.location_name = location_name
        self.location_with_context = location_with_context
        self.reasoning = reasoning
        self.cache_key = self._make_cache_key(location_name) if location_name else None

    @staticmethod
    def _make_cache_key(location_name: str) -> str:
        """Generate a standardized cache key from a canonical location name."""
        normalized = location_name.lower().strip()
        return f"geocode:{hashlib.md5(normalized.encode()).hexdigest()}"


PROVIDER = "bedrock"
MODEL_ID = "amazon.nova-pro-v1:0"


@observe(name="extract_spatial_from_query")
def _extract_spatial_with_llm(query: str) -> SpatialExtractionResult | None:  # pylint: disable=too-many-branches,too-many-return-statements
    """LLM-only spatial extraction used by the public wrapper.

    Args:
        query: Natural language description potentially containing spatial info.

    Returns:
        SpatialExtractionResult (location name, contextual phrase, reasoning, cache key),
        or None when no spatial signal is found; raises on LLM setup/errors.
    """
    try:
        client = instructor.from_provider(f"{PROVIDER}/{MODEL_ID}")
    except Exception as e:
        if LANGFUSE:
            LANGFUSE.update_current_trace(
                tags=["error", "client_init_error"],
                metadata={"error_type": "client_init_error", "message": str(e), "success": False},
            )
        raise RuntimeError(
            f"Failed to initialize instructor client with provider '{PROVIDER}' and model '{MODEL_ID}': {e}"
        ) from e

    today = datetime.now(UTC).strftime("%Y-%m-%d")
    prompt_path = Path(__file__).parent / "prompts" / "spatial_extraction.md"

    if not prompt_path.exists():
        raise FileNotFoundError(f"Required prompt file not found: {prompt_path}")

    with open(prompt_path, encoding="utf-8") as f:
        system_prompt = f.read().replace("{current_date}", today)

    try:
        from pydantic import BaseModel

        class SpatialExtractionOutput(BaseModel):
            """Output model for spatial extraction from LLM."""
            location_name: str | None = None
            location_with_context: str | None = None
            reasoning: str | None = None

        output = client.create(
            modelId=MODEL_ID,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query},
            ],
            response_model=SpatialExtractionOutput,
        )

        if not output.location_name and not output.location_with_context:
            return None

        return SpatialExtractionResult(
            location_name=output.location_name,
            location_with_context=output.location_with_context,
            reasoning=output.reasoning,
        )
    except Exception as e:
        if LANGFUSE:
            LANGFUSE.update_current_trace(
                tags=["error", "llm_error"],
                metadata={"error_type": "llm_error", "message": str(e), "success": False},
            )
        raise RuntimeError(f"Failed to extract spatial info from query '{query}': {e}") from e

    if LANGFUSE:
        LANGFUSE.update_current_trace(
            tags=["success", "spatial_extraction"],
            metadata={"success": True, "canonical_name": output.location_name},
        )


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
    extraction = _extract_spatial_with_llm(query)
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
                if LANGFUSE:
                    LANGFUSE.update_current_trace(
                        tags=["cache_hit", "success"],
                        metadata={"cache_hit": True, "canonical_name": canonical_name},
                    )
                logger.debug("Cache hit for location: %s (key: %s)", canonical_name, cache_key)
                return SpatialConstraint(
                    location=location_to_geocode,
                    wkt_geometry=cached_geom,
                    reasoning=f"{extraction.reasoning} (cached)",
                )
        except (redis.RedisError, Exception) as e:
            logger.debug("Cache lookup failed: %s", e)

    # Cache miss or cache disabled - geocode the location
    try:
        geom = convert_text_to_geom(location_to_geocode)

        if geom is None:
            logger.warning("Failed to geocode location: %s", location_to_geocode)
            if LANGFUSE:
                LANGFUSE.update_current_trace(
                    tags=["cache_miss", "error", "geocoding_failed"],
                    metadata={"error_type": "geocoding_failed", "success": False},
                )
            return SpatialConstraint(
                location=location_to_geocode,
                wkt_geometry=None,
                reasoning=extraction.reasoning,
            )

        geom_str = str(geom)

        # Store in cache
        if cache and canonical_name:
            try:
                cache_key = extraction.cache_key
                cache.set(cache_key, geom_str, ttl=900)
            except (redis.RedisError, Exception) as e:
                logger.debug("Cache store failed: %s", e)

        if LANGFUSE:
            LANGFUSE.update_current_trace(
                tags=["cache_miss", "success", "geocoded"],
                metadata={
                    "cache_hit": False,
                    "success": True,
                    "geometry_type": type(geom).__name__,
                },
            )

        logger.debug("Successfully geocoded location: %s (%s)", canonical_name, location_to_geocode)
        return SpatialConstraint(
            location=location_to_geocode,
            wkt_geometry=geom_str,
            reasoning=extraction.reasoning,
        )

    except (ValueError, TypeError) as e:
        logger.warning("Invalid location format for '%s': %s", location_to_geocode, e)
        if LANGFUSE:
            LANGFUSE.update_current_trace(
                tags=["error", "validation_error"],
                metadata={"error_type": "validation_error"},
            )
        return SpatialConstraint(
            location=location_to_geocode,
            wkt_geometry=None,
            reasoning=extraction.reasoning,
        )

    except Exception as e:
        logger.error("Unexpected error geocoding '%s': %s", location_to_geocode, e)
        if LANGFUSE:
            LANGFUSE.update_current_trace(
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
