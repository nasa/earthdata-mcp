"""NASA KMS (Keyword Management System) API client."""

import logging
from dataclasses import dataclass
from functools import lru_cache

import requests

logger = logging.getLogger(__name__)

KMS_BASE_URL = "https://cmr.earthdata.nasa.gov/kms"


@dataclass
class KMSTerm:
    """Represents a term from KMS with its metadata."""

    uuid: str
    scheme: str
    term: str
    definition: str | None


class KMSClient:
    """Client for NASA's Keyword Management System API."""

    def __init__(self, base_url: str = KMS_BASE_URL):
        self.base_url = base_url

    def lookup_term(self, term: str, scheme: str) -> KMSTerm | None:
        """
        Look up a term in KMS and return its full metadata.

        Args:
            term: The term to look up (e.g., "MODIS", "TERRA", "PRECIPITATION")
            scheme: KMS concept scheme (e.g., "sciencekeywords", "platforms", "instruments")

        Returns:
            KMSTerm with uuid, scheme, term, and definition, or None if not found.
        """
        return _lookup_term_cached(term, scheme, self.base_url)


@lru_cache(maxsize=2000)
def _lookup_term_cached(term: str, scheme: str, base_url: str) -> KMSTerm | None:
    """
    Cached lookup of a KMS term.

    Module-level cache shared across all client instances to avoid
    duplicate API calls for the same term.
    """
    search_url = f"{base_url}/concepts/concept_scheme/{scheme}/pattern/{term}"

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

    # Find the best matching concept
    uuid = _extract_uuid_from_search(data, term)
    if not uuid:
        logger.debug("No UUID found for term '%s' in %s", term, scheme)
        return None

    # Fetch the full concept details
    definition = _fetch_concept_definition(uuid, base_url)

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


def _fetch_concept_definition(uuid: str, base_url: str) -> str | None:
    """Fetch definition for a concept by UUID."""
    concept_url = f"{base_url}/concept/{uuid}"

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


# Convenience function for simple lookups
def lookup_term(term: str, scheme: str) -> KMSTerm | None:
    """
    Look up a term in KMS.

    Convenience function that uses a default client.

    Args:
        term: The term to look up
        scheme: KMS concept scheme

    Returns:
        KMSTerm or None if not found
    """
    return _lookup_term_cached(term, scheme, KMS_BASE_URL)


def clear_cache() -> None:
    """Clear the KMS lookup cache. Useful for testing."""
    _lookup_term_cached.cache_clear()
