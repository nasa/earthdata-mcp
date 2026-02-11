"""
Granule availability validation utilities for discover_data orchestrator.

Validates collections by checking for actual granule data within spatio-temporal
constraints using CMR's granule endpoint.
"""

import hashlib
import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError, as_completed
from datetime import datetime
from io import BytesIO

from langfuse import observe
from shapely import wkt as shapely_wkt
from shapely.geometry import mapping

from tools.models.output_model import CollectionMatch
from util.cache import get_cache_client
from util.cmr.client import CMRError, search_cmr

logger = logging.getLogger(__name__)

GRANULE_VALIDATION_MAX_WORKERS = int(os.environ.get("GRANULE_VALIDATION_MAX_WORKERS", "5"))


@observe(name="count_granules")
def _count_granules(
    collection_concept_id: str,
    temporal_start: datetime | None = None,
    temporal_end: datetime | None = None,
    spatial_wkt: str | None = None,
) -> tuple[int, int]:
    """
    Count granules for a collection with optional temporal/spatial constraints.

    Args:
        collection_concept_id: CMR collection concept ID
        temporal_start: Optional start datetime for temporal constraint
        temporal_end: Optional end datetime for temporal constraint
        spatial_wkt: Optional WKT geometry string for spatial constraint

    Returns:
        Tuple of (hits_count, took_ms) where:
        - hits_count: Number of granules matching constraints
        - took_ms: Time taken by CMR (from CMR-Took header)

    Raises:
        CMRError: If the request fails
    """
    params = {"collection_concept_id": collection_concept_id, "page_size": 0}

    # Add temporal constraint if provided
    if temporal_start is not None and temporal_end is not None:
        params["temporal"] = f"{temporal_start.isoformat()}Z,{temporal_end.isoformat()}Z"

    # Prepare shapefile if spatial constraint provided
    files = None
    if spatial_wkt:
        geom = shapely_wkt.loads(spatial_wkt)
        geojson = {
            "type": "FeatureCollection",
            "features": [{"type": "Feature", "geometry": mapping(geom), "properties": {}}],
        }
        file_obj = BytesIO(json.dumps(geojson).encode("utf-8"))
        files = {"shapefile": ("shapefile", file_obj, "application/geo+json")}

    # Use search_cmr to make the request
    try:
        # Get first (and only) page - we only need the count, not the items
        for page in search_cmr(
            concept_type="granule",
            search_params=params,
            page_size=0,
            method="POST" if files else "GET",
            files=files,
        ):
            return page.total_hits, page.took_ms

        # If no pages returned (shouldn't happen), return 0
        logger.warning("No response from CMR for %s", collection_concept_id)
        return 0, 0

    except CMRError as e:
        logger.error(
            "CMR granule count failed for %s: %s",
            collection_concept_id,
            e,
        )
        raise


def _build_cache_key(
    concept_id: str,
    temporal_start: datetime | None,
    temporal_end: datetime | None,
    spatial_wkt: str | None,
) -> str:
    """
    Build cache key for granule count result.

    Args:
        concept_id: CMR collection concept ID
        temporal_start: Optional start datetime
        temporal_end: Optional end datetime
        spatial_wkt: Optional WKT geometry string

    Returns:
        Cache key string
    """
    constraint_str = f"{temporal_start}|{temporal_end}|{spatial_wkt}"
    constraint_hash = hashlib.sha256(constraint_str.encode()).hexdigest()
    return f"granule_count:{concept_id}:{constraint_hash}"


def _get_cache_ttl(is_ongoing: bool) -> int:
    """
    Determine cache TTL based on whether collection is ongoing.

    Args:
        is_ongoing: Whether the collection is still actively collecting data

    Returns:
        TTL in seconds (900 for ongoing, 86400 for completed)
    """
    return 900 if is_ongoing else 86400


def _validate_single_collection(
    collection: CollectionMatch,
    temporal_start: datetime | None,
    temporal_end: datetime | None,
    spatial_wkt: str | None,
) -> tuple[int, int]:
    """
    Validate a single collection by counting its granules.

    Args:
        collection: Collection to validate
        temporal_start: Optional start datetime
        temporal_end: Optional end datetime
        spatial_wkt: Optional WKT geometry string

    Returns:
        Tuple of (hits_count, took_ms)
    """
    return _count_granules(
        collection.concept_id,
        temporal_start,
        temporal_end,
        spatial_wkt,
    )


@observe(name="validate_granule_availability")
def validate_granule_availability(
    collections: list[CollectionMatch],
    temporal_start: datetime | None,
    temporal_end: datetime | None,
    spatial_wkt: str | None,
) -> list[CollectionMatch]:
    """
    Validate granule availability for collections with spatio-temporal constraints.

    Checks each collection for granules within the constraints. Collections with zero granules
    are filtered out. Results are cached with TTL based on whether collections are ongoing.

    Args:
        collections: List of collections to validate
        temporal_start: Optional start datetime for temporal constraint
        temporal_end: Optional end datetime for temporal constraint
        spatial_wkt: Optional WKT geometry string for spatial constraint

    Returns:
        list[CollectionMatch] with granule_count > 0
    """
    cache = get_cache_client()

    failures = 0
    zero_granule_count = 0

    # Check cache first for all collections
    futures_to_collection = {}
    with ThreadPoolExecutor(max_workers=GRANULE_VALIDATION_MAX_WORKERS) as executor:
        for collection in collections:
            cache_key = _build_cache_key(
                collection.concept_id,
                temporal_start,
                temporal_end,
                spatial_wkt,
            )

            # Try cache first
            cached_result = cache.get(cache_key)
            if cached_result:
                cached_data = json.loads(cached_result)
                collection.granule_count = cached_data["count"]
            else:
                # Submit for parallel validation
                future = executor.submit(
                    _validate_single_collection,
                    collection,
                    temporal_start,
                    temporal_end,
                    spatial_wkt,
                )
                futures_to_collection[future] = collection

        # Process results as they complete (scale timeout with collection count)
        timeout = max(60, len(futures_to_collection) * 2)
        try:
            for future in as_completed(futures_to_collection, timeout=timeout):
                collection = futures_to_collection[future]
                try:
                    hits_count = future.result()
                    collection.granule_count = hits_count

                    # Cache the result
                    cache_key = _build_cache_key(
                        collection.concept_id,
                        temporal_start,
                        temporal_end,
                        spatial_wkt,
                    )
                    ttl = _get_cache_ttl(collection.is_ongoing)
                    cache.set(
                        cache_key,
                        json.dumps({"count": hits_count, "timestamp": time.time()}),
                        ttl=ttl,
                    )

                except Exception as e:
                    logger.warning(
                        "Granule validation failed for %s: %s (type: %s)",
                        collection.concept_id,
                        e,
                        type(e).__name__,
                        exc_info=True,
                    )
                    failures += 1
                    # Keep collection with None granule_count
                    collection.granule_count = None

        except TimeoutError:
            logger.warning("Granule availability check timed out for some collections")
            failures += len(futures_to_collection)

    # Filter out collections with zero granules
    validated = []
    for collection in collections:
        if collection.granule_count is not None and collection.granule_count > 0:
            validated.append(collection)
        elif collection.granule_count == 0:
            zero_granule_count += 1

    if zero_granule_count > 0 or failures > 0:
        logger.info(
            "Granule availability: %d/%d collections validated (filtered %d with no granules, %d failures)",
            len(validated),
            len(collections),
            zero_granule_count,
            failures,
        )

    return validated
