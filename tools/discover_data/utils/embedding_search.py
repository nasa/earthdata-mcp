"""
Embedding-based search for collections and related entities.

Searches across all entity types (collections, variables, instruments, etc.)
to find relevant matches via semantic similarity.
"""

import logging
from typing import Any

from langfuse import observe

from util.datastores import get_datastore
from util.embeddings import BedrockEmbeddingGenerator

logger = logging.getLogger(__name__)

# Module-level singleton for embedding generator (lazy initialized)
_embedding_generator: BedrockEmbeddingGenerator | None = None


def get_embedding_generator() -> BedrockEmbeddingGenerator:
    """Get or create the embedding generator singleton."""
    global _embedding_generator  # pylint: disable=global-statement
    if _embedding_generator is None:
        _embedding_generator = BedrockEmbeddingGenerator()
    return _embedding_generator


@observe(name="generate_query_embedding")
def generate_query_embedding(query_text: str) -> list[float]:
    """
    Generate an embedding vector for a search query.

    Args:
        query_text: The natural language query text

    Returns:
        1024-dimensional embedding vector
    """
    generator = get_embedding_generator()
    return generator.generate(query_text)


@observe(name="search_collections")
def search_collections(
    query_text: str,
    similarity_threshold: float = 0.5,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """
    Search for collections semantically similar to the query.

    Args:
        query_text: Natural language query
        similarity_threshold: Minimum similarity score (0-1)
        limit: Maximum number of results

    Returns:
        List of matching collection records with fields:
        - type: "collection"
        - external_id: CMR concept ID
        - attribute: Which field matched (title, abstract, etc.)
        - text_content: The matched text
        - similarity: Similarity score (0-1)
    """
    embedding = generate_query_embedding(query_text)
    datastore = get_datastore()

    results = datastore.search_similar(
        embedding=embedding,
        limit=limit,
        entity_type="collection",
    )

    # Filter by similarity threshold
    filtered = [r for r in results if r["similarity"] >= similarity_threshold]

    logger.info(
        "Collection search for '%s': %d results (threshold %.2f)",
        query_text[:50],
        len(filtered),
        similarity_threshold,
    )

    return filtered


@observe(name="search_all_entity_types")
def search_all_entity_types(
    query_text: str,
    similarity_threshold: float = 0.5,
    limit: int = 30,
) -> list[dict[str, Any]]:
    """
    Search across all entity types (collections, variables, citations, KMS terms).

    Used for indirect matching when direct collection search yields few results.

    Args:
        query_text: Natural language query
        similarity_threshold: Minimum similarity score (0-1)
        limit: Maximum number of results

    Returns:
        List of matching records from any entity type, with fields:
        - type: Entity type (collection, variable, citation, instruments, platforms, sciencekeywords)
        - external_id: Entity identifier
        - attribute: Which field matched
        - text_content: The matched text
        - similarity: Similarity score (0-1)
    """
    embedding = generate_query_embedding(query_text)
    datastore = get_datastore()

    # Search without entity_type filter to get all types
    results = datastore.search_similar(
        embedding=embedding,
        limit=limit,
        entity_type=None,
    )

    # Filter by similarity threshold
    filtered = [r for r in results if r["similarity"] >= similarity_threshold]

    # Log breakdown by type
    type_counts = {}
    for r in filtered:
        t = r["type"]
        type_counts[t] = type_counts.get(t, 0) + 1

    logger.info(
        "All-type search for '%s': %d results %s (threshold %.2f)",
        query_text[:50],
        len(filtered),
        type_counts,
        similarity_threshold,
    )

    return filtered


@observe(name="search_by_entity_type")
def search_by_entity_type(
    query_text: str,
    entity_type: str,
    similarity_threshold: float = 0.5,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """
    Search for entities of a specific type.

    Args:
        query_text: Natural language query
        entity_type: Type to search (collection, variable, citation,
                    instruments, platforms, sciencekeywords)
        similarity_threshold: Minimum similarity score (0-1)
        limit: Maximum number of results

    Returns:
        List of matching records of the specified type
    """
    embedding = generate_query_embedding(query_text)
    datastore = get_datastore()

    results = datastore.search_similar(
        embedding=embedding,
        limit=limit,
        entity_type=entity_type,
    )

    filtered = [r for r in results if r["similarity"] >= similarity_threshold]

    logger.info(
        "Search %s for '%s': %d results (threshold %.2f)",
        entity_type,
        query_text[:50],
        len(filtered),
        similarity_threshold,
    )

    return filtered


def deduplicate_by_external_id(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Deduplicate results by external_id, keeping highest similarity.

    When the same entity matches on multiple attributes (title and abstract),
    keep only the highest-scoring match.

    Args:
        results: List of search results

    Returns:
        Deduplicated list with one entry per external_id
    """
    best_by_id: dict[str, dict[str, Any]] = {}

    for result in results:
        ext_id = result["external_id"]
        if ext_id not in best_by_id or result["similarity"] > best_by_id[ext_id]["similarity"]:
            best_by_id[ext_id] = result

    # Return in order of similarity (highest first)
    return sorted(best_by_id.values(), key=lambda r: r["similarity"], reverse=True)
