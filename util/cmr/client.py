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

# UMM-T tool types surfaced to clients — others (e.g. "Algorithm") are not
# user-facing links and are excluded from exploration_links.
_ALLOWED_TOOL_TYPES = frozenset({"Web User Interface", "Web Portal"})

CONCEPT_ENDPOINTS = {
    "collection": "/search/collections.umm_json",
    "variable": "/search/variables.umm_json",
    "citation": "/search/citations.umm_json",
    "granule": "/search/granules.umm_json",
    "tool": "/search/tools.umm_json",
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


def fetch_collection_tags(concept_id: str) -> dict[str, Any]:
    """
    Fetch CMR tags for a collection using the JSON endpoint.

    Unlike the UMM-JSON endpoint, the JSON endpoint supports ``include_tags``
    which exposes EDSC-managed tags such as ``edsc.extra.serverless.gibs``.

    Args:
        concept_id: The CMR collection concept ID.

    Returns:
        Tags dict keyed by tag name (e.g. ``{"edsc.extra.serverless.gibs": {"data": [...]}}``)
        Returns empty dict if request fails or collection has no tags.
    """
    url = f"{CMR_URL}/search/collections.json"
    params = {"concept_id": concept_id, "include_tags": "edsc.*"}

    try:
        response = requests.get(url, params=params, headers={"Client-Id": CLIENT_ID}, timeout=30)
        response.raise_for_status()
        data = response.json()
        items = data.get("feed", {}).get("entry", [])
        if items:
            return items[0].get("tags", {})
        return {}
    except requests.RequestException as e:
        logger.warning("Failed to fetch tags for %s: %s", concept_id, e)
        return {}


def _extract_tool_info(umm_t_item: dict[str, Any]) -> dict[str, Any] | None:
    """
    Extract client-actionable fields from a UMM-T item.

    Pulls the PotentialAction URL template and its typed query inputs so the
    client can construct a parameterised deep link (e.g. "Open in Giovanni").

    Args:
        umm_t_item: A single UMM-T item from CMR (with 'meta' and 'umm' keys).

    Returns:
        Dictionary with tool link fields: name, url_template, query_inputs.
        Returns None when the UMM-T item is not an allowed tool type.
    """
    umm = umm_t_item.get("umm", {})

    # Only surface Web UI / Web Portal tools — skip algorithms, services, etc.
    tool_type = umm.get("Type")
    if tool_type not in _ALLOWED_TOOL_TYPES:
        return None

    potential_action = umm.get("PotentialAction", {})

    # Only accept SearchAction — other PotentialAction types (e.g. ViewAction)
    # are not suitable as pre-parameterised exploration links.
    action_type = potential_action.get("Type") if potential_action else None
    if action_type is not None and action_type != "SearchAction":
        return None

    target = potential_action.get("Target", {})

    query_inputs = [
        {
            "value_name": qi.get("ValueName"),
            "value_type": qi.get("ValueType"),
            "required": qi.get("ValueRequired", False),
        }
        for qi in potential_action.get("QueryInput", [])
    ]

    # Base URL from UMM URL entry
    base_url = (umm.get("URL") or {}).get("URLValue")

    # Topic from ToolKeywords (e.g. "DATA ANALYSIS AND VISUALIZATION")
    keywords = umm.get("ToolKeywords") or []
    raw_topic = keywords[0].get("ToolTopic") if keywords else None
    topic = raw_topic.capitalize() if raw_topic else None

    return {
        "name": umm.get("Name"),
        "base_url": base_url,
        "url_template": target.get("UrlTemplate"),
        "query_inputs": query_inputs,
        "topic": topic,
    }


def fetch_tool_metadata(tool_concept_ids: list[str]) -> list[dict[str, Any]]:
    """
    Fetch UMM-T metadata for a list of tool concept IDs.

    Batches all IDs into a single CMR request and extracts the client-actionable
    fields needed to construct 'Open in X' actions (name, url, type, etc.).

    Args:
        tool_concept_ids: List of tool concept IDs (e.g. ["TL1234-PROV"]).

    Returns:
        List of dicts with actionable tool fields extracted from UMM-T.
        Returns empty list if no IDs provided, request fails, or no tools found.
    """
    if not tool_concept_ids:
        return []

    url = f"{CMR_URL}/search/tools.umm_json"
    params = {"concept_id[]": tool_concept_ids, "page_size": len(tool_concept_ids)}

    try:
        response = requests.get(url, params=params, headers={"Client-Id": CLIENT_ID}, timeout=30)
        response.raise_for_status()
        items = response.json().get("items", [])
        return [t for item in items if (t := _extract_tool_info(item)) is not None]
    except requests.RequestException as e:
        logger.warning("Failed to fetch tool metadata for %s: %s", tool_concept_ids, e)
        return []


def search_cmr(
    concept_type: str,
    search_params: dict[str, Any],
    page_size: int = 500,
    search_after: str | None = None,
    method: Literal["GET", "POST"] = "GET",
    files: dict[str, Any] | None = None,
) -> Generator[CMRSearchResponse]:
    """
    Search CMR and yield pages of results using search-after pagination.

    Args:
        concept_type: Type of concept (collection, variable, citation, granule)
        search_params: Dictionary of CMR search parameters
        page_size: Number of results per page
        search_after: Optional search-after token for continuing an existing query
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
    if search_after:
        headers["CMR-Search-After"] = search_after
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
