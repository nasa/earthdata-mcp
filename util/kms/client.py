"""NASA KMS (Keyword Management System) API client with Redis caching.

Uses scheme-level caching: fetches entire concept schemes and stores them in
Redis HASHes for O(1) term lookups. This avoids hitting the KMS API with
concurrent pattern-match requests that can overwhelm the gateway.
"""

import logging
from urllib.parse import quote

import requests

from models.cmr import KMSTerm
from util.cache import get_cache_client

logger = logging.getLogger(__name__)

KMS_BASE_URL = "https://cmr.earthdata.nasa.gov/kms"
KMS_CACHE_TTL = 86400  # 24 hours - KMS terms are very static


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


def _get_scheme_cache_key(scheme: str) -> str:
    """Generate Redis HASH key for a KMS scheme."""
    return f"kms:scheme:{scheme}"


_KMS_PAGE_SIZE = 2000


def _parse_concepts(data: dict) -> dict[str, dict]:
    """Extract terms from a KMS API response page."""
    terms = {}
    for concept in data.get("concepts", []):
        pref_label = concept.get("prefLabel")
        uuid = concept.get("uuid")

        if not pref_label or not uuid:
            continue

        definition = None
        definitions = concept.get("definitions", [])
        if definitions and isinstance(definitions, list) and isinstance(definitions[0], dict):
            definition = definitions[0].get("text")

        # Uppercase key for case-insensitive lookup
        terms[pref_label.upper()] = {
            "uuid": uuid,
            "term": pref_label,
            "definition": definition,
        }

    return terms


def _fetch_scheme(scheme: str) -> dict[str, dict]:
    """
    Fetch all concepts in a scheme from the KMS API.

    Paginates through all pages — the API returns at most 2,000 terms
    per page and the sciencekeywords scheme has 3,600+.

    Returns:
        Dict mapping uppercase term to {uuid, term, definition}
    """
    encoded_scheme = quote(scheme, safe="")
    url = f"{KMS_BASE_URL}/concepts/concept_scheme/{encoded_scheme}"

    # First page
    response = requests.get(
        url,
        params={"format": "json", "page_size": _KMS_PAGE_SIZE},
        timeout=60,
    )
    response.raise_for_status()
    data = response.json()

    terms = _parse_concepts(data)
    total_hits = data.get("hits", len(terms))

    # Fetch remaining pages
    page = 2
    while len(terms) < total_hits:
        response = requests.get(
            url,
            params={"format": "json", "page_size": _KMS_PAGE_SIZE, "page_num": page},
            timeout=60,
        )
        response.raise_for_status()
        page_data = response.json()

        new_terms = _parse_concepts(page_data)
        if not new_terms:
            break

        terms.update(new_terms)
        page += 1

    logger.info("Fetched %d terms from KMS scheme '%s' (%d pages)", len(terms), scheme, page - 1)
    return terms


_FETCH_MAX_RETRIES = 3
_FETCH_RETRY_DELAY = 2  # seconds

_LOCK_TTL = 60  # seconds — margin over the ~10-15s a paginated KMS fetch takes


def _get_lock_key(scheme: str) -> str:
    """Generate Redis lock key for a KMS scheme fetch."""
    return f"kms:lock:{scheme}"


def warm_scheme(scheme: str) -> str:
    """Non-blocking cache warm for a single KMS scheme.

    Called by the WarmKMSCache step function state.  Returns immediately in
    every path so the Lambda never idles:

    - ``"cached"``  — scheme already in Redis
    - ``"fetched"`` — this invocation fetched from KMS and cached it
    - ``"locked"``  — another Lambda holds the fetch lock; caller should retry

    On fetch failure the lock is released and ``"locked"`` is returned so the
    Step Function retries via its Wait state.
    """
    cache = get_cache_client()
    cache_key = _get_scheme_cache_key(scheme)

    if cache.hexists(cache_key):
        return "cached"

    lock_key = _get_lock_key(scheme)
    if not cache.setnx(lock_key, "1", _LOCK_TTL):
        return "locked"

    # We hold the lock — fetch, cache, release
    try:
        terms = _fetch_scheme(scheme)
    except (requests.RequestException, ValueError) as e:
        logger.warning("Failed to fetch KMS scheme '%s' during warm: %s", scheme, e)
        cache.delete(lock_key)
        return "locked"

    if not terms:
        logger.warning("KMS scheme '%s' returned no terms during warm", scheme)
        cache.delete(lock_key)
        return "locked"

    if not cache.hmset(cache_key, terms, ttl=KMS_CACHE_TTL):
        logger.warning("Failed to cache KMS scheme '%s' during warm", scheme)

    cache.delete(lock_key)
    return "fetched"


def _ensure_scheme_cached(scheme: str) -> dict[str, dict] | None:
    """
    Ensure a KMS scheme is cached in Redis, or fetch it.

    Called during lookup after the WarmKMSCache step has already run, so the
    cache is expected to be warm.  Falls back to fetching directly on cache
    miss (e.g. TTL expiry mid-pipeline).

    Returns:
        {} (empty dict) if scheme is already cached
        None on fetch errors or empty terms
        dict of fetched terms if fetch succeeded (whether or not caching worked)
    """
    cache = get_cache_client()

    cache_key = _get_scheme_cache_key(scheme)
    if cache.hexists(cache_key):
        return {}

    # Cache miss — fetch directly (warm step should have handled this)
    terms = None
    for attempt in range(_FETCH_MAX_RETRIES):
        try:
            terms = _fetch_scheme(scheme)
        except (requests.RequestException, ValueError) as e:
            logger.warning(
                "Failed to fetch KMS scheme '%s' (attempt %d/%d): %s",
                scheme,
                attempt + 1,
                _FETCH_MAX_RETRIES,
                e,
            )
            if cache.hexists(cache_key):
                logger.info("KMS scheme '%s' now in cache (populated by another Lambda)", scheme)
                return {}
            continue

        if not terms:
            logger.warning("KMS scheme '%s' returned no terms", scheme)
            return None

        if not cache.hmset(cache_key, terms, ttl=KMS_CACHE_TTL):
            logger.warning("Failed to cache KMS scheme '%s', serving from fetch", scheme)

        return terms

    logger.error("All %d attempts to fetch KMS scheme '%s' failed", _FETCH_MAX_RETRIES, scheme)
    return None


def lookup_term(term: str, scheme: str) -> KMSTerm | None:
    """
    Look up a single term in KMS.

    Args:
        term: The term to look up (e.g., "MODIS", "TERRA")
        scheme: KMS concept scheme (e.g., "sciencekeywords", "platforms", "instruments")

    Returns:
        KMSTerm or None if not found
    """
    results = lookup_terms([(term, scheme)])
    return results.get((term, scheme))


def lookup_terms(terms: list[tuple[str, str]]) -> dict[tuple[str, str], KMSTerm | None]:
    """
    Look up multiple terms in KMS with Redis caching.

    Optimized batch lookup: groups terms by scheme, ensures each scheme is
    cached once, then uses HMGET for batch retrieval.

    Args:
        terms: List of (term, scheme) tuples

    Returns:
        Dict mapping (term, scheme) to KMSTerm or None
    """
    if not terms:
        return {}

    cache = get_cache_client()
    results: dict[tuple[str, str], KMSTerm | None] = {}

    # Group terms by scheme for batch operations
    by_scheme: dict[str, list[str]] = {}
    for term, scheme in terms:
        if scheme not in by_scheme:
            by_scheme[scheme] = []
        by_scheme[scheme].append(term)

    # Process each scheme
    for scheme, scheme_terms in by_scheme.items():
        # Ensure scheme is cached or fetched
        scheme_data = _ensure_scheme_cached(scheme)

        if scheme_data is None:
            # Failed to fetch - mark all terms from this scheme as not found
            for term in scheme_terms:
                results[(term, scheme)] = None
            continue

        fields = [t.upper() for t in scheme_terms]

        if scheme_data:
            # Use freshly fetched data directly
            term_values = scheme_data
        else:
            # Scheme is cached - batch lookup from Redis HASH
            cache_key = _get_scheme_cache_key(scheme)
            term_values = cache.hmget(cache_key, fields)

        # Map results back to original terms
        for term, upper_term in zip(scheme_terms, fields, strict=True):
            cached = term_values.get(upper_term)
            if cached:
                results[(term, scheme)] = KMSTerm(
                    uuid=cached["uuid"],
                    scheme=scheme,
                    term=cached["term"],
                    definition=cached.get("definition"),
                )
            else:
                results[(term, scheme)] = None

    return results


_KMS_SCHEMES = ("sciencekeywords", "platforms", "instruments")


def clear_cache() -> None:
    """Delete all cached KMS scheme hashes so the next lookup re-fetches from the API."""
    cache = get_cache_client()
    for scheme in _KMS_SCHEMES:
        key = _get_scheme_cache_key(scheme)
        if cache.delete(key):
            logger.info("Cleared KMS cache for scheme '%s'", scheme)
        else:
            logger.debug("No cache entry to clear for scheme '%s'", scheme)
