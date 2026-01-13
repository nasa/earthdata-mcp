"""
CMR Collections Embeddings Tool

This module provides functionality to search NASA's Common Metadata Repository (CMR)
collections using natural language queries and semantic search capabilities.
"""

import hashlib
import json
import os
from typing import Any, Dict

import redis
from langfuse import observe, get_client

from util.abstract_db import AbstractDBConnection
from util.cmr_utils import reorder_results, wkt_to_cmr_params
from util.data_collection import fetch_cmr_data
from util.embedding import create_embedding_generator
from util.natural_language_geocoder import convert_text_to_geom
from util.postgres_db import PostgresDBConnection
from util.redis_client import CacheClient
from util.request_utils import parse_format

from tools.collections_embeddings.input_model import CollectionsEmbeddingsInput
from tools.collections_embeddings.output_model import (
    CollectionsEmbeddingsOutput,
    DatasetSummary,
)

cmr_url = os.getenv("CMR_URL")

# Initialize clients
langfuse = get_client()
cache = CacheClient()

db = PostgresDBConnection()

# Load supported models configuration
with open("util/supported-models.json", "r", encoding="utf-8") as f:
    supported_models = json.load(f)

embedding_generator = create_embedding_generator(supported_models)


@observe(name="get_concept_ids")
def get_concept_ids(db_backend: AbstractDBConnection, query_params):
    """
    Retrieve concept IDs based on cosine similarity to the query embedding.

    This function searches the database for concept IDs that are most similar
    to the provided query embedding using cosine similarity.
    """
    result = db_backend.search(query_params)
    if not result:
        return []

    return result


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


def is_valid_bracket_structure(geometry_str: str) -> bool:
    """
    Validate that a geometry string has properly matched brackets.

    Checks for balanced parentheses in WKT geometry strings.

    Args:
        geometry_str: The geometry string to validate

    Returns:
        True if all brackets are properly matched, False otherwise
    """
    if not geometry_str:
        return False

    stack = []
    bracket_pairs = {"(": ")", "[": "]", "{": "}"}

    for char in geometry_str:
        if char in bracket_pairs:
            stack.append(char)
        elif char in bracket_pairs.values():
            if not stack:
                return False
            opening = stack.pop()
            if bracket_pairs[opening] != char:
                return False

    return len(stack) == 0


@observe(name="process_spatial_query")
def process_spatial_query(spatial_query) -> Dict[str, Any]:
    """
    Process spatial query and return geometry if valid.

    Validates the geometry from the spatial query. If the geometry is invalid or truncated,
    attempts to retrieve it from cache using the geoLocation. Updates Langfuse trace with
    cache hit/miss information.

    Args:
        spatial_query: A GeospatialOutput object containing geometry and geoLocation

    Returns:
        Dictionary with 'geometry' key if valid geometry found, empty dict otherwise
    """
    result = {}

    if not spatial_query or not spatial_query.success or not spatial_query.geometry:
        return result

    geometry_str = spatial_query.geometry

    # Check if geometry is valid and not truncated
    # A valid WKT geometry should contain proper structure
    if (
        not geometry_str
        or len(geometry_str) < 10
        or not any(
            keyword in geometry_str.upper()
            for keyword in ["POINT", "POLYGON", "MULTIPOLYGON", "LINESTRING"]
        )
        or not is_valid_bracket_structure(geometry_str)
    ):
        # Geometry is nonsensical, try to retrieve from cache using geoLocation
        if spatial_query.geoLocation:
            # Check cache first
            cached_result = get_from_cache(spatial_query.geoLocation)
            if cached_result and cached_result.get("geometry"):
                cached_result["from_cache"] = True
                langfuse.update_current_trace(
                    tags=["cache_hit", "success"],
                    metadata={
                        "cache_hit": True,
                        "location": spatial_query.geoLocation,
                        "location_length": len(spatial_query.geoLocation),
                    },
                )
                result["geometry"] = convert_text_to_geom(cached_result["geometry"])
            else:
                # Cache miss - geometry cannot be retrieved
                langfuse.update_current_trace(
                    tags=["cache_miss", "geometry_retrieval_failed"],
                    metadata={
                        "cache_hit": False,
                        "location": spatial_query.geoLocation,
                    },
                )
    else:
        # Geometry looks valid, use it directly
        result["geometry"] = convert_text_to_geom(geometry_str)

    return result


def _build_cmr_params(concept_ids: list, query_params: dict, page_size: int) -> dict:
    """Build CMR API parameters.

    Args:
        concept_ids: List of CMR concept IDs to fetch
        query_params: Dictionary containing optional geometry, start_date, end_date
        page_size: Number of results per page

    Returns:
        Dictionary of CMR API parameters
    """
    cmr_param = {
        "concept_id[]": concept_ids,
        "include_granule_counts": "true",
        "options[spatial][or]": "true",
        "page_size": page_size,
    }

    if "geometry" in query_params and query_params["geometry"]:
        spatial_params = wkt_to_cmr_params(query_params["geometry"])
        cmr_param.update(spatial_params)

    if "start_date" in query_params and "end_date" in query_params:
        start_date_cmr = query_params["start_date"].replace("+00:00", "Z")
        end_date_cmr = query_params["end_date"].replace("+00:00", "Z")
        cmr_param["temporal[]"] = f"{start_date_cmr},{end_date_cmr}"

    return cmr_param


def _parse_cmr_item(item: dict, response_format: str) -> DatasetSummary:
    """Parse a CMR item into a DatasetSummary.

    Args:
        item: CMR response item
        response_format: Response format (umm_json or json)

    Returns:
        DatasetSummary object
    """
    if response_format == "umm_json":
        concept_id = item["meta"]["concept-id"]
        title = item["umm"].get("EntryTitle", "")
        abstract = item["umm"].get("Abstract", "")
    else:  # json format
        concept_id = item["id"]
        title = item.get("title", "")
        abstract = item.get("summary", "")

    return DatasetSummary(
        concept_id=concept_id,
        title=title,
        abstract=abstract,
    )


@observe(name="fetch_cmr_collections_metadata")
def fetch_cmr_collections_metadata(
    concept_ids: list,
    similarity_scores: list,
    query_params: dict,
    page_size: int = 10,
) -> CollectionsEmbeddingsOutput:
    """Fetch collections metadata from CMR and format as CollectionsEmbeddingsOutput.

    Args:
        concept_ids: List of CMR concept IDs to fetch
        similarity_scores: List of similarity scores corresponding to concept_ids
        query_params: Dictionary containing optional geometry, start_date, end_date
        page_size: Number of results per page

    Returns:
        CollectionsEmbeddingsOutput model with results and count
    """
    if not concept_ids:
        return CollectionsEmbeddingsOutput(results=[], count=0)

    cmr_param = _build_cmr_params(concept_ids, query_params, page_size)
    response_format = parse_format(".")
    response = fetch_cmr_data(
        cmr_url=f"{cmr_url}/search/collections.{response_format}",
        method="GET",
        params=cmr_param,
    )

    if not response["success"]:
        langfuse.update_current_trace(
            tags=["cmr_error"],
            metadata={
                "error": response["error"],
                "status_code": response["status_code"],
            },
        )
        return CollectionsEmbeddingsOutput(results=[], count=0)

    ordered_items = reorder_results(
        response, concept_ids, response_format, similarity_scores
    )

    dataset_summaries = [
        _parse_cmr_item(item, response_format) for item in ordered_items
    ]

    result = CollectionsEmbeddingsOutput(
        results=dataset_summaries,
        count=len(dataset_summaries),
    )

    langfuse.update_current_trace(
        tags=["cmr_success"],
        metadata={
            "collection_count": len(dataset_summaries),
            "response_format": response_format,
        },
    )

    return result


@observe(name="search_cmr_collections_embeddings")
def search_cmr_collections_embeddings(
    query: CollectionsEmbeddingsInput,
) -> Any:
    """Get a list of collections from CMR based on embeddings search.

    NOTE: This function is not yet implemented.
    Args:
        query: A CollectionsEmbeddingsInput model containing the search text.

    Returns:
        A list of dictionaries containing dataset summaries with concept_id, title, and abstract.
    """
    # Check if query string is empty

    db.connect()

    query_embedding = embedding_generator.generate_embedding(query.query)

    query_info = {"query": query.query}

    # Prepare query parameters
    query_params = {
        "page": query.page_num,
        "query_embedding": query_embedding,
        "query_size": query.page_size,
    }

    start_date = None
    end_date = None

    # Handle spatial query from GeospatialOutput
    spatial_query = query.spatial
    if spatial_query:
        spatial_result = process_spatial_query(spatial_query)
        if spatial_result.get("geometry"):
            query_params["geometry"] = spatial_result["geometry"]

    # Parse Temporal from query input
    temporal_input = query.temporal
    if temporal_input:
        start_date = temporal_input.StartDate
        end_date = temporal_input.EndDate

        if start_date or end_date:
            query_info["temporal"] = {}
            if start_date:
                query_params["start_date"] = start_date.isoformat()
                query_info["temporal"]["startDate"] = start_date.isoformat()
            if end_date:
                query_params["end_date"] = end_date.isoformat()
                query_info["temporal"]["endDate"] = end_date.isoformat()
    else:
        start_date = end_date = None

    # Fetch concept IDs and their similarity scores from the database
    db_search = get_concept_ids(db, query_params)

    concept_ids = []
    similarity_scores = []

    # Iterate through the database search results
    # Adds the concept ID (first element) to the concept_ids list
    # Adds the similarity score (last element) to the similarity_scores list
    for item in db_search:
        concept_ids.append(item[0])
        similarity_scores.append(item[-1])

    # Fetch CMR collections metadata and format as CollectionsEmbeddingsOutput
    result = fetch_cmr_collections_metadata(
        concept_ids=concept_ids,
        similarity_scores=similarity_scores,
        query_params=query_params,
        page_size=query.page_size,
    )

    return result.model_dump()
