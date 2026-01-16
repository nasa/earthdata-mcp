"""Langfuse client utility."""

import logging

from langfuse import Langfuse

logger = logging.getLogger(__name__)

_langfuse_client: Langfuse | None = None
_initialized: bool = False


def get_langfuse() -> Langfuse | None:
    """
    Get the Langfuse client instance.

    Returns None if Langfuse fails to initialize (e.g., missing credentials).
    Uses lazy initialization with caching.
    """
    global _langfuse_client, _initialized

    if _initialized:
        return _langfuse_client

    try:
        _langfuse_client = Langfuse()
        _initialized = True
    except Exception as e:
        logger.warning("Failed to initialize Langfuse: %s", e)
        _langfuse_client = None
        _initialized = True

    return _langfuse_client


def flush_langfuse() -> None:
    """Flush any pending Langfuse events."""
    if _langfuse_client:
        _langfuse_client.flush()
