"""
Collection hydration utilities for discover_data orchestrator.

Transforms embedding search results into fully hydrated CollectionMatch objects
by fetching metadata from the collections table.
"""

import logging
from datetime import datetime
from typing import Any

from langfuse import observe

from tools.discover_data.utils.resolution_parsing import (
    extract_instruments,
    extract_platforms,
    parse_resolution_info,
    parse_temporal_coverage,
)
from tools.models.output_model import CollectionMatch
from util.datastores import get_datastore

logger = logging.getLogger(__name__)


@observe(name="hydrate_collections")
def hydrate_collections(
    ranked_results: list[dict[str, Any]],
    temporal_start: datetime | None = None,
    temporal_end: datetime | None = None,
    spatial_wkt: str | None = None,
) -> list[CollectionMatch]:
    """
    Transform scored embedding results into hydrated CollectionMatch objects.

    Fetches metadata from the collections table and uses resolution parsing
    to populate resolution, temporal_coverage, platforms, and instruments.

    Applies temporal and spatial filtering at the database level.

    Args:
        ranked_results: Scored collection results from embedding search/scoring
        temporal_start: Optional start date - exclude collections that end before this
        temporal_end: Optional end date - exclude collections that start after this
        spatial_wkt: Optional WKT geometry - exclude collections that don't intersect

    Returns:
        List of fully hydrated CollectionMatch objects (filtered by constraints)
    """
    # Filter to collection results only
    collection_results = [r for r in ranked_results if r.get("type") == "collection"]

    if not collection_results:
        return []

    # Fetch metadata for all collections in one batch, with constraint filtering
    concept_ids = [r["external_id"] for r in collection_results]
    datastore = get_datastore()
    collection_data = datastore.fetch_collections_by_ids(
        concept_ids,
        temporal_start=temporal_start,
        temporal_end=temporal_end,
        spatial_wkt=spatial_wkt,
    )

    logger.debug(
        "Hydrating %d collections (%d found in database)",
        len(collection_results),
        len(collection_data),
    )

    matches = []
    for result in collection_results:
        concept_id = result["external_id"]

        # Skip collections that were filtered out by temporal/spatial constraints
        if concept_id not in collection_data:
            logger.debug("Skipping collection %s (filtered by constraints)", concept_id)
            continue

        data = collection_data[concept_id]
        metadata = data.get("metadata", {})

        # Skip if metadata is empty
        if not metadata:
            logger.debug("Skipping collection %s (no metadata found)", concept_id)
            continue

        # Parse resolution and coverage from metadata
        resolution = parse_resolution_info(metadata)
        temporal_coverage = parse_temporal_coverage(metadata)
        platforms = extract_platforms(metadata)
        instruments = extract_instruments(metadata)

        # Get title from metadata if available, fall back to embedding result
        title = metadata.get("EntryTitle") or result.get("text_content", "")
        abstract = metadata.get("Abstract")

        match = CollectionMatch(
            concept_id=concept_id,
            title=title,
            abstract=abstract,
            similarity_score=result.get("similarity", 0.0),
            match_type=result.get("match_type", "direct"),
            matched_attribute=result.get("attribute"),
            resolution=resolution,
            temporal_coverage=temporal_coverage,
            platforms=platforms,
            instruments=instruments,
            related_entity_id=result.get("related_entity_id"),
            related_entity_text=result.get("related_entity_text"),
        )
        matches.append(match)

    logger.info(
        "Hydrated %d collection matches",
        len(matches),
    )

    return matches
