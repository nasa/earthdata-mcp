"""
Association search utilities for discover_data orchestrator.

Queries the associations table to find collections related to
non-collection entities (citations, variables, science keywords, etc.)
"""

import logging
from typing import Any

from langfuse import observe

from util.datastores import get_datastore

logger = logging.getLogger(__name__)


@observe(name="get_collections_for_entities")
def get_collections_for_entities(
    entities: list[tuple[str, str]],
) -> dict[str, list[str]]:
    """
    Batch lookup of collections for multiple entities.

    Args:
        entities: List of (entity_id, entity_type) tuples

    Returns:
        Dict mapping entity_id to list of collection IDs
    """
    if not entities:
        return {}

    datastore = get_datastore()
    results = datastore.get_collections_for_entities(entities)

    total_collections = sum(len(cids) for cids in results.values())
    logger.debug(
        "Batch lookup for %d entities found %d total collection associations",
        len(entities),
        total_collections,
    )

    return results


@observe(name="enrich_indirect_matches")
def enrich_indirect_matches(
    embedding_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Enrich non-collection embedding results with associated collection IDs.

    For each non-collection result (citation, variable, etc.), finds
    the collections associated with it and adds that information.

    Args:
        embedding_results: List of embedding search results that may include
            non-collection types

    Returns:
        List of results with 'associated_collections' field added for
        non-collection types
    """
    # Separate collection results from non-collection results
    collection_results = []
    non_collection_results = []

    for result in embedding_results:
        if result.get("type") == "collection":
            collection_results.append(result)
        else:
            non_collection_results.append(result)

    # Batch lookup for efficiency
    if non_collection_results:
        entities = [(r["external_id"], r["type"]) for r in non_collection_results]
        collections_map = get_collections_for_entities(entities)

        # Enrich non-collection results
        for result in non_collection_results:
            entity_id = result["external_id"]
            associated = collections_map.get(entity_id, [])
            result["associated_collections"] = associated

    # Return all results (collections don't need enrichment)
    return collection_results + non_collection_results


def expand_to_collections(
    embedding_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Convert non-collection matches to collection matches via associations.

    Takes embedding results that may include non-collection entities and
    returns a list of collection records that can be enriched with CMR metadata.

    Args:
        embedding_results: List of embedding search results (any type)

    Returns:
        List of collection-like records with:
        - external_id: Collection concept ID
        - type: "collection"
        - match_type: How the collection was found (e.g., "via_citation")
        - related_entity_id: ID of the entity that led to this collection
        - related_entity_text: Text content of the matching entity
        - similarity: Original similarity score of the related entity
    """
    # First enrich with associations
    enriched = enrich_indirect_matches(embedding_results)

    collection_records = []
    seen_collection_ids = set()

    for result in enriched:
        entity_type = result.get("type")

        if entity_type == "collection":
            # Direct collection match
            if result["external_id"] not in seen_collection_ids:
                seen_collection_ids.add(result["external_id"])
                collection_records.append(
                    {
                        "external_id": result["external_id"],
                        "type": "collection",
                        "match_type": "direct",
                        "attribute": result.get("attribute"),
                        "text_content": result.get("text_content"),
                        "similarity": result.get("similarity", 0.0),
                        "related_entity_id": None,
                        "related_entity_text": None,
                    }
                )
        else:
            # Non-collection - expand to associated collections
            associated = result.get("associated_collections", [])
            match_type = f"via_{entity_type}"

            for collection_id in associated:
                if collection_id not in seen_collection_ids:
                    seen_collection_ids.add(collection_id)
                    collection_records.append(
                        {
                            "external_id": collection_id,
                            "type": "collection",
                            "match_type": match_type,
                            "attribute": None,  # Will be filled by CMR enrichment
                            "text_content": None,
                            "similarity": result.get("similarity", 0.0),
                            "related_entity_id": result["external_id"],
                            "related_entity_text": result.get("text_content"),
                        }
                    )

    # Sort by similarity (highest first)
    collection_records.sort(key=lambda r: r["similarity"], reverse=True)

    logger.info(
        "Expanded %d embedding results to %d unique collections",
        len(embedding_results),
        len(collection_records),
    )

    return collection_records
