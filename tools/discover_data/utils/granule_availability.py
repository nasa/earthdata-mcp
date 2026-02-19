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
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from io import BytesIO

from langfuse import observe
from shapely import wkt as shapely_wkt
from shapely.geometry import mapping

from tools.models.output_model import CollectionMatch
from util.cache import get_cache_client
from util.cmr.client import search_cmr

logger = logging.getLogger(__name__)


class GranuleValidationError(Exception):
    """Raised when one or more collections fail CMR granule validation."""


GRANULE_VALIDATION_MAX_WORKERS = int(os.environ.get("GRANULE_VALIDATION_MAX_WORKERS", "10"))


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

    if temporal_start is not None or temporal_end is not None:
        # Format as ISO 8601 with Z suffix (CMR requires this format)
        # Replace timezone offset with Z to avoid "+00:00Z" which CMR rejects
        start_str = (
            temporal_start.isoformat().replace("+00:00", "Z") if temporal_start is not None else ""
        )
        end_str = (
            temporal_end.isoformat().replace("+00:00", "Z") if temporal_end is not None else ""
        )
        params["temporal"] = f"{start_str},{end_str}"

    files = None
    if spatial_wkt:
        geom = shapely_wkt.loads(spatial_wkt)
        geojson = {
            "type": "FeatureCollection",
            "features": [{"type": "Feature", "geometry": mapping(geom), "properties": {}}],
        }
        file_obj = BytesIO(json.dumps(geojson).encode("utf-8"))
        files = {"shapefile": ("shapefile", file_obj, "application/geo+json")}

    # page_size=0: CMR only populates total_hits, not items — one response page is all we need
    page = next(
        search_cmr(
            concept_type="granule",
            search_params=params,
            page_size=0,
            method="POST",
            files=files,
        ),
        None,
    )

    if page is None:
        logger.warning("No response from CMR for %s", collection_concept_id)
        return 0, 0

    return page.total_hits, page.took_ms


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
        list[CollectionMatch] where granule_count > 0 or granule_count is None (validation failed)
    """
    # Only validate if constraints exist - without them, assume exploratory search
    if not (temporal_start or temporal_end) and not spatial_wkt:
        logger.info("Skipping granule validation - no spatial or temporal constraints")
        return collections

    if not collections:
        return collections

    cache = get_cache_client()

    failures = 0
    zero_granule_count = 0

    pending_validations = {}
    with ThreadPoolExecutor(max_workers=GRANULE_VALIDATION_MAX_WORKERS) as executor:
        for collection in collections:
            cache_key = _build_cache_key(
                collection.concept_id,
                temporal_start,
                temporal_end,
                spatial_wkt,
            )

            cached_result = cache.get(cache_key)
            if cached_result:
                collection.granule_count = cached_result["count"]
            else:
                task = executor.submit(
                    _count_granules,
                    collection.concept_id,
                    temporal_start,
                    temporal_end,
                    spatial_wkt,
                )
                pending_validations[task] = collection

        for task in as_completed(pending_validations):
            collection = pending_validations[task]
            try:
                hits_count, _ = task.result()
                collection.granule_count = hits_count

                cache_key = _build_cache_key(
                    collection.concept_id,
                    temporal_start,
                    temporal_end,
                    spatial_wkt,
                )
                ttl = _get_cache_ttl(collection.is_ongoing)
                cache.set(
                    cache_key,
                    {"count": hits_count, "timestamp": time.time()},
                    ttl=ttl,
                )

            except Exception:
                logger.warning(
                    "Granule validation failed for %s",
                    collection.concept_id,
                    exc_info=True,
                )
                failures += 1

    if failures > 0:
        raise GranuleValidationError(
            f"CMR granule validation failed for {failures} of "
            f"{len(pending_validations)} collection(s)"
        )

    validated = []
    for collection in collections:
        if collection.granule_count > 0:
            validated.append(collection)
        else:
            zero_granule_count += 1

    if zero_granule_count > 0 or failures > 0:
        logger.info(
            "Granule availability: %d/%d collections validated "
            "(filtered %d with no granules, %d failures)",
            len(validated),
            len(collections),
            zero_granule_count,
            failures,
        )

    return validated
