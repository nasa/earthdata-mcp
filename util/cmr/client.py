"""CMR API client for fetching concept metadata."""

import logging
import os
from collections.abc import Generator
from typing import Any, Literal

import requests
from pydantic import BaseModel, Field

from util.environment import get_client_id

logger = logging.getLogger(__name__)

CMR_URL = os.environ.get("CMR_URL", "https://cmr.earthdata.nasa.gov")


CLIENT_ID = get_client_id()

CONCEPT_ENDPOINTS = {
    "collection": "/search/collections.umm_json",
    "variable": "/search/variables.umm_json",
    "citation": "/search/citations.umm_json",
    "granule": "/search/granules.umm_json",
}


class CMRSearchResponse(BaseModel):
    """Single page of CMR search results with metadata."""

    items: list[dict[str, Any]] = Field(description="List of concept metadata dictionaries")
    total_hits: int = Field(
        description="Total number of results matching the query (from CMR-Hits header)"
    )
    took_ms: int = Field(
        description="Time CMR spent processing the request in milliseconds (from CMR-Took header)"
    )
    search_after: str | None = Field(
        default=None, description="Token for fetching the next page (from CMR-Search-After header)"
    )
    page_size: int = Field(description="Number of items in this page")


class CMRError(Exception):
    """Raised when a CMR API request fails."""


def fetch_concept(concept_id: str, revision_id: str) -> dict[str, Any]:
    """
    Fetch concept metadata from CMR.

    Args:
        concept_id: The CMR concept ID (e.g., C1234-PROVIDER).
        revision_id: The revision ID.

    Returns:
        The concept metadata as a dictionary.

    Raises:
        CMRError: If the request fails.
    """
    url = f"{CMR_URL}/search/concepts/{concept_id}/{revision_id}.umm_json"

    try:
        response = requests.get(url, headers={"Client-Id": CLIENT_ID}, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        raise CMRError(f"Failed to fetch {concept_id} from CMR: {e}") from e


def fetch_associations(concept_id: str) -> dict[str, Any]:
    """
    Fetch associations for a collection from CMR.

    Args:
        concept_id: The CMR collection concept ID.

    Returns:
        Dictionary of associations (variables, citations).
        Returns empty dict if request fails or no associations found.
    """
    url = f"{CMR_URL}/search/collections.umm_json"
    params = {"concept_id": concept_id, "include_has_granules": "false"}

    try:
        response = requests.get(url, params=params, headers={"Client-Id": CLIENT_ID}, timeout=30)
        response.raise_for_status()
        data = response.json()
        items = data.get("items", [])
        if items:
            return items[0].get("meta", {}).get("associations", {})
        return {}
    except requests.RequestException as e:
        logger.warning("Failed to fetch associations for %s: %s", concept_id, e)
        return {}


def search_cmr(
    concept_type: str,
    search_params: dict[str, Any],
    page_size: int = 500,
    method: Literal["GET", "POST"] = "GET",
    files: dict[str, Any] | None = None,
) -> Generator[CMRSearchResponse]:
    """
    Search CMR and yield pages of results using search-after pagination.

    Args:
        concept_type: Type of concept (collection, variable, citation, granule)
        search_params: Dictionary of CMR search parameters
        page_size: Number of results per page
        method: HTTP method to use ("GET" or "POST")
        files: Optional files dict for multipart/form-data (e.g., shapefile)

    Yields:
        CMRSearchResponse objects containing items and metadata

    Raises:
        CMRError: If the concept_type is unsupported or the request fails.
    """
    if concept_type not in CONCEPT_ENDPOINTS:
        raise CMRError(
            f"Unsupported concept_type: {concept_type}. Supported: {list(CONCEPT_ENDPOINTS.keys())}"
        )

    endpoint = f"{CMR_URL}{CONCEPT_ENDPOINTS[concept_type]}"
    params = {**search_params, "page_size": page_size}
    headers = {"Client-Id": CLIENT_ID}
    total_fetched = 0

    while True:
        logger.info(
            "Fetching %s (page_size=%d, fetched=%d)", concept_type, page_size, total_fetched
        )

        try:
            if method.upper() == "POST":
                # POST request with optional files for spatial queries
                response = requests.post(
                    endpoint, data=params, files=files, headers=headers, timeout=60
                )
            else:
                response = requests.get(endpoint, params=params, headers=headers, timeout=60)

            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            raise CMRError(f"CMR request failed: {e}") from e

        items = data.get("items", [])
        total_hits = int(response.headers.get("CMR-Hits", 0))
        took_ms = int(response.headers.get("CMR-Took", 0))
        search_after_token = response.headers.get("CMR-Search-After")

        # For count-only queries (page_size=0), return one page with empty items
        if page_size == 0:
            logger.info("Count-only query: %d total hits", total_hits)
            yield CMRSearchResponse(
                items=[],
                total_hits=total_hits,
                took_ms=took_ms,
                search_after=None,
                page_size=0,
            )
            break

        if not items:
            logger.info("No more results")
            break

        total_fetched += len(items)
        logger.info(
            "Fetched %d items (total: %d, hits: %d, took: %dms)",
            len(items),
            total_fetched,
            total_hits,
            took_ms,
        )

        yield CMRSearchResponse(
            items=items,
            total_hits=total_hits,
            took_ms=took_ms,
            search_after=search_after_token,
            page_size=len(items),
        )

        # Get search-after token for next page
        if not search_after_token or len(items) < page_size:
            logger.info("Fetched all %d items", total_fetched)
            break

        headers["CMR-Search-After"] = search_after_token
