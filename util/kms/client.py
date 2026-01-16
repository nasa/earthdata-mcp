"""NASA KMS (Keyword Management System) API client."""

import logging
from functools import lru_cache

import requests

from util.models import KMSTerm

logger = logging.getLogger(__name__)

KMS_BASE_URL = "https://cmr.earthdata.nasa.gov/kms"


@lru_cache(maxsize=2000)
def _lookup_term_cached(term: str, scheme: str) -> KMSTerm | None:
    """Cached lookup of a KMS term."""
    search_url = f"{KMS_BASE_URL}/concepts/concept_scheme/{scheme}/pattern/{term}"

    try:
        response = requests.get(search_url, params={"format": "json"}, timeout=10)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        logger.debug("KMS search failed for '%s' in %s: %s", term, scheme, e)
        return None
    except ValueError as e:
        logger.debug("Failed to parse KMS JSON response for '%s': %s", term, e)
        return None

    uuid = _extract_uuid_from_search(data, term)
    if not uuid:
        logger.debug("No UUID found for term '%s' in %s", term, scheme)
        return None

    definition = _fetch_concept_definition(uuid)

    return KMSTerm(
        uuid=uuid,
        scheme=scheme,
        term=term,
        definition=definition,
    )


def _extract_uuid_from_search(data: dict, term: str) -> str | None:
    """Extract UUID for best matching concept from JSON search results."""
    try:
        concepts = data.get("concepts", [])

        # Look for exact match first (case-insensitive)
        for concept in concepts:
            pref_label = concept.get("prefLabel", "")
            uuid = concept.get("uuid")
            if pref_label.upper() == term.upper() and uuid:
                return uuid

        # Fall back to first result
        if concepts:
            return concepts[0].get("uuid")

    except (KeyError, TypeError, IndexError) as e:
        logger.debug("Failed to extract UUID from KMS response: %s", e)

    return None


def _fetch_concept_definition(uuid: str) -> str | None:
    """Fetch definition for a concept by UUID."""
    concept_url = f"{KMS_BASE_URL}/concept/{uuid}"

    try:
        response = requests.get(concept_url, params={"format": "json"}, timeout=10)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        logger.debug("KMS concept fetch failed for '%s': %s", uuid, e)
        return None
    except ValueError as e:
        logger.debug("Failed to parse KMS concept JSON for '%s': %s", uuid, e)
        return None

    return data.get("definition")


def lookup_term(term: str, scheme: str) -> KMSTerm | None:
    """
    Look up a term in KMS.

    Args:
        term: The term to look up (e.g., "MODIS", "TERRA", "PRECIPITATION")
        scheme: KMS concept scheme (e.g., "sciencekeywords", "platforms", "instruments")

    Returns:
        KMSTerm or None if not found
    """
    return _lookup_term_cached(term, scheme)


def clear_cache() -> None:
    """Clear the KMS lookup cache. Useful for testing."""
    _lookup_term_cached.cache_clear()
