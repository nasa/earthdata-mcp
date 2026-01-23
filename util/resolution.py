"""
Shared resolution utilities for temporal and spatial disambiguation.

This module provides generic helpers to reduce duplication between
the parallel temporal.py and spatial.py implementations.
"""

from collections.abc import Callable
from typing import Any, Protocol


class Resolution(Protocol):
    """Protocol for resolution objects that can be stringified and have a unit."""

    unit: str

    def __str__(self) -> str: ...


def group_by_resolution(
    collections: list[dict[str, Any]],
    extract_fn: Callable[[dict[str, Any]], Resolution | None],
) -> dict[str | None, list[dict[str, Any]]]:
    """
    Group collections by their resolution using the provided extraction function.

    Args:
        collections: List of collection metadata dicts
        extract_fn: Function to extract resolution from a collection

    Returns:
        Dict mapping resolution string to collections
    """
    groups: dict[str | None, list[dict[str, Any]]] = {}

    for collection in collections:
        resolution = extract_fn(collection)
        key = str(resolution) if resolution else None
        groups.setdefault(key, []).append(collection)

    return groups


def check_disambiguation(
    collections: list[dict[str, Any]],
    extract_fn: Callable[[dict[str, Any]], Resolution | None],
    exclude_units: tuple[str, ...],
    sort_key_fn: Callable[[str], float],
) -> tuple[bool, list[str]]:
    """
    Check if collections need disambiguation based on resolution differences.

    Args:
        collections: List of collection metadata dicts
        extract_fn: Function to extract resolution from a collection
        exclude_units: Units to exclude from disambiguation (e.g., "Varies", "Constant")
        sort_key_fn: Function to compute sort key from resolution string

    Returns:
        Tuple of (needs_disambiguation, list of distinct resolutions found)
    """
    resolutions: set[str] = set()

    for collection in collections:
        resolution = extract_fn(collection)
        if resolution and resolution.unit not in exclude_units:
            resolutions.add(str(resolution))

    needs_disambiguation = len(resolutions) > 1
    return needs_disambiguation, sorted(resolutions, key=sort_key_fn)
