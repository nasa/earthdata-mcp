"""NASA KMS (Keyword Management System) API client."""

import logging
from urllib.parse import quote

import requests

logger = logging.getLogger(__name__)

KMS_BASE_URL = "https://cmr.earthdata.nasa.gov/kms"


def search_kms_pattern(query: str, scheme: str | None = None) -> list[dict]:
    """
    Search KMS across all schemes or a specific scheme using a pattern match.

    This performs a live, un-cached query against the KMS REST API.
    The pattern endpoints perform substring matching by default.

    Args:
        query: The substring pattern to search for (e.g., 'moisture').
        scheme: Optional KMS scheme (e.g., 'sciencekeywords') to restrict results.

    Returns:
        List of matching concept dictionaries containing uuid, prefLabel,
        definitions, and scheme. Returns an empty list if no matches found.

    Raises:
        requests.RequestException: If the KMS API request fails.
    """
    encoded_query = quote(query, safe="")

    if scheme:
        encoded_scheme = quote(scheme, safe="")
        url = f"{KMS_BASE_URL}/concepts/concept_scheme/{encoded_scheme}/pattern/{encoded_query}"
    else:
        url = f"{KMS_BASE_URL}/concepts/pattern/{encoded_query}"

    response = requests.get(url, params={"format": "json"}, timeout=10)
    response.raise_for_status()
    data = response.json()

    # The API includes a 'hits' field at the top level
    total_hits = data.get("hits", 0)

    if total_hits == 0:
        return []

    return data.get("concepts", [])
