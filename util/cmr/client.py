"""CMR API client for fetching concept metadata."""

import logging
import os
from collections.abc import Generator
from typing import Any

import requests

logger = logging.getLogger(__name__)

CMR_URL = os.environ.get("CMR_URL", "https://cmr.earthdata.nasa.gov")

CONCEPT_ENDPOINTS = {
    "collection": "/search/collections.umm_json",
    "variable": "/search/variables.umm_json",
    "citation": "/search/citations.umm_json",
}


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
        response = requests.get(url, timeout=30)
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
        response = requests.get(url, params=params, timeout=30)
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
) -> Generator[list[dict[str, Any]]]:
    """
    Search CMR and yield pages of results.

    Args:
        concept_type: Type of concept (collection, variable, citation)
        search_params: Dictionary of CMR search parameters
        page_size: Number of results per page

    Yields:
        Lists of concept metadata dictionaries

    Raises:
        CMRError: If the concept_type is unsupported or the request fails.
    """
    if concept_type not in CONCEPT_ENDPOINTS:
        raise CMRError(
            f"Unsupported concept_type: {concept_type}. "
            f"Supported: {list(CONCEPT_ENDPOINTS.keys())}"
        )

    endpoint = f"{CMR_URL}{CONCEPT_ENDPOINTS[concept_type]}"

    params = {**search_params, "page_size": page_size}
    page_num = 1
    total_fetched = 0

    while True:
        params["page_num"] = page_num
        logger.info("Fetching %s page %d (page_size=%d)", concept_type, page_num, page_size)

        try:
            response = requests.get(endpoint, params=params, timeout=60)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            raise CMRError(f"CMR request failed: {e}") from e

        items = data.get("items", [])
        if not items:
            logger.info("No more results, stopping pagination")
            break

        total_fetched += len(items)
        logger.info(
            "Fetched %d items (total: %d, hits: %s)",
            len(items),
            total_fetched,
            data.get("hits", "unknown"),
        )

        yield items

        hits = data.get("hits", 0)
        if total_fetched >= hits:
            logger.info("Fetched all %d items", total_fetched)
            break

        page_num += 1
