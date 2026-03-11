"""
Tool association enrichment for discover_data collections.

This module is the discover_data-facing orchestration entrypoint for tool-link
enrichment. It composes dedicated helper modules for Earthdata Search,
Worldview/GIBS, CMR UMM tool-link resolution, and shared geometry parsing.

Temporal behavior by link type is intentionally not uniform:
- Earthdata Search: only applies temporal query params when user-extracted
    temporal constraints are present.
- Worldview/GIBS: may fall back to collection end date for initial time/layer
    usability when user temporal constraints are absent.
- UMM-T templates: resolve temporal values from user constraints only.

These decisions are documented in each link-generation helper module so policy
and implementation remain colocated.
"""

import contextvars
import hashlib
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from urllib.parse import urlsplit

from langfuse import observe

from models.tools.discover_data import CollectionMatch, SpatialConstraint, TemporalConstraint
from util.cache import get_cache_client
from util.cmr.client import fetch_associations, fetch_collection_tags, fetch_tool_metadata

from .earthdata_search_links import _EARTHDATA_SEARCH_BASE, _earthdata_search_link
from .umm_tool_links import _prioritize_tools, _resolve_tool_url
from .worldview_links import (
    _WORLDVIEW_BASE,
    _all_gibs_layers,
    _worldview_link,
)

logger = logging.getLogger(__name__)


class ToolAssociationError(Exception):
    """Raised when any collection fails CMR tool association enrichment."""


TOOL_ASSOC_MAX_WORKERS = int(os.environ.get("TOOL_ASSOC_MAX_WORKERS", "10"))

# UMM-T associations are slow-moving — 24h TTL is safe
TOOL_ASSOC_CACHE_TTL = 86400


def _base_key(url: str) -> str:
    """Return a scheme-agnostic URL key for base-url comparisons."""
    parsed = urlsplit(url)
    return f"{parsed.netloc}{parsed.path}".rstrip("/").lower()


def _matches_base_ignoring_scheme(url: str, canonical_base: str) -> bool:
    """Return True when url points at canonical_base regardless of http vs https."""
    return _base_key(url).startswith(_base_key(canonical_base))


def _build_exploration_links(  # pylint: disable=too-many-arguments
    tools: list[dict],
    concept_id: str,
    temporal: TemporalConstraint | None,
    spatial: SpatialConstraint | None,
    short_name: str | None,
    gibs_layers: list[str],
    collection_end_date: datetime | None = None,
) -> list[dict]:
    """
    Build the full ordered exploration links list for a collection.

    Keeps stable ordering and behavior:
    1. Guaranteed Earthdata Search link
    2. Guaranteed Worldview link when GIBS layers are present
    3. Prioritized CMR UMM tool links, deduplicated against guaranteed links
    """
    links: list[dict] = [_earthdata_search_link(concept_id, temporal, spatial, collection_end_date)]
    guaranteed_worldview_link_added = False

    if gibs_layers:
        links.append(_worldview_link(gibs_layers, temporal, spatial, collection_end_date))
        guaranteed_worldview_link_added = True

    for tool in _prioritize_tools(tools):
        base = (tool.get("base_url") or "").rstrip("/")

        # Dedup against guaranteed links:
        # - Earthdata Search is always guaranteed, so always dedup Earthdata-based tools.
        # - Worldview is guaranteed only when GIBS layers were available.
        is_earthdata_base = _matches_base_ignoring_scheme(base, _EARTHDATA_SEARCH_BASE)
        is_worldview_base = _matches_base_ignoring_scheme(base, _WORLDVIEW_BASE)
        if is_earthdata_base:
            continue
        if is_worldview_base and guaranteed_worldview_link_added:
            continue

        resolved_tool = _resolve_tool_url(
            tool, concept_id, temporal, spatial, short_name, gibs_layers=gibs_layers
        )
        if resolved_tool is not None:
            links.append(resolved_tool)

    return links


def _cache_key(concept_id: str) -> str:
    """
    Build cache key for tool association result.

    Args:
        concept_id: CMR collection concept ID

    Returns:
        Cache key string
    """
    key_hash = hashlib.sha256(concept_id.encode()).hexdigest()
    return f"tool_associations:{concept_id}:{key_hash}"


@observe(name="fetch_tool_associations")
def _fetch_tool_associations(concept_id: str) -> list[dict]:
    """
    Fetch tool associations for a single collection from CMR.

    Makes two parallel CMR calls (associations + tags), then one sequential
    call to resolve UMM-T metadata for any tool IDs found.

    Args:
        concept_id: CMR collection concept ID

    Returns:
        Dict with ``tools`` (list of UMM-T tool dicts) and ``tags`` (CMR collection
        tags dict).  Both can be empty if the collection has no associations or tags.
    """
    # fetch_associations and fetch_collection_tags are independent — run in parallel
    with ThreadPoolExecutor(max_workers=2) as pool:
        assoc_future = pool.submit(fetch_associations, concept_id)
        tags_future = pool.submit(fetch_collection_tags, concept_id)
        associations = assoc_future.result()
        tags = tags_future.result()

    tool_ids = associations.get("tools", [])
    if not tool_ids:
        return {"tools": [], "tags": tags}

    tools = fetch_tool_metadata(tool_ids)
    if not tools:
        raise ToolAssociationError(f"Failed to fetch tool metadata for {concept_id}")

    return {"tools": tools, "tags": tags}


@observe(name="enrich_with_tool_associations")
def enrich_with_tool_associations(
    collections: list[CollectionMatch],
    temporal: TemporalConstraint | None = None,
    spatial: SpatialConstraint | None = None,
) -> list[CollectionMatch]:
    """
    Enrich collections with UMM-T tool associations, resolving URLs from context.

    Checks each collection for CMR-defined tools that can open or access its data.
    Each tool's URL template is expanded using the current temporal/spatial context
    and the collection's concept ID, so the client receives a ready-to-use link.
    Collections with no associated tools receive an empty list. Raw templates are
    cached for 24 hours; URL resolution happens at request time. Any failure raises
    ToolAssociationError immediately.

    Args:
        collections: List of collections to enrich.
        temporal: Temporal constraint from the current search (used to pre-fill dates).
        spatial: Spatial constraint from the current search (used to pre-fill bbox).

    Returns:
        The same list of collections with exploration_links populated.

    Raises:
        ToolAssociationError: If any collection fails tool association enrichment.
    """
    if not collections:
        return collections

    cache = get_cache_client()

    pending: dict = {}

    with ThreadPoolExecutor(max_workers=TOOL_ASSOC_MAX_WORKERS) as executor:
        for collection in collections:
            key = _cache_key(collection.concept_id)
            cached = cache.get(key)

            if cached is not None:
                tags = cached.get("tags", {})
                cov = collection.temporal_coverage
                gibs_layers = _all_gibs_layers(
                    tags,
                    spatial,
                    temporal=temporal,
                    collection_end_date=cov.end_date if cov else None,
                )
                collection.exploration_links = _build_exploration_links(
                    cached["tools"],
                    collection.concept_id,
                    temporal,
                    spatial,
                    collection.short_name,
                    gibs_layers,
                    collection_end_date=cov.end_date if cov else None,
                )
            else:
                ctx = contextvars.copy_context()
                task = executor.submit(
                    ctx.run,
                    _fetch_tool_associations,
                    collection.concept_id,
                )
                pending[task] = collection

        for task in as_completed(pending):
            collection = pending[task]
            try:
                result = task.result()
                tools = result["tools"]
                tags = result.get("tags", {})
                cov = collection.temporal_coverage
                gibs_layers = _all_gibs_layers(
                    tags,
                    spatial,
                    temporal=temporal,
                    collection_end_date=cov.end_date if cov else None,
                )
                collection.exploration_links = _build_exploration_links(
                    tools,
                    collection.concept_id,
                    temporal,
                    spatial,
                    collection.short_name,
                    gibs_layers,
                    collection_end_date=cov.end_date if cov else None,
                )

                key = _cache_key(collection.concept_id)
                cache.set(
                    key,
                    {"tools": tools, "tags": tags, "timestamp": time.time()},
                    ttl=TOOL_ASSOC_CACHE_TTL,
                )
            except ToolAssociationError:
                raise
            except Exception as exc:
                raise ToolAssociationError(
                    f"Failed to fetch tool associations for {collection.concept_id}"
                ) from exc

    return collections
