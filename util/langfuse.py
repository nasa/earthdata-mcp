"""Langfuse client utility."""

import logging
import os

from langfuse import Langfuse, get_client

from util.ssm import get_parameter

logger = logging.getLogger(__name__)

_initialized: bool = False


def _configure_langfuse() -> None:
    """Configure Langfuse credentials from SSM if not already set."""
    global _initialized

    if _initialized:
        return

    try:
        environment = os.environ.get("ENVIRONMENT_NAME")
        if environment and not os.environ.get("LANGFUSE_SECRET_KEY"):
            ssm_parameter = f"{environment}-langfuse-secret-key"
            secret_key = get_parameter(ssm_parameter)
            if secret_key:
                os.environ["LANGFUSE_SECRET_KEY"] = secret_key
        _initialized = True
    except Exception as e:
        logger.warning("Failed to configure Langfuse credentials: %s", e)
        _initialized = True


def get_langfuse() -> Langfuse | None:
    """
    Get the Langfuse client instance.

    Returns None if Langfuse fails to initialize (e.g., missing credentials).
    """
    _configure_langfuse()

    try:
        return get_client()
    except Exception as e:
        logger.warning("Failed to initialize Langfuse: %s", e)
        return None


def flush_langfuse() -> None:
    """Flush any pending Langfuse events."""
    try:
        client = get_client()
        client.flush()
    except Exception:
        pass


def initialize_langfuse_client() -> Langfuse | None:
    """
    Initialize module-level Langfuse client for use in utility modules.

    This function is designed to be called at module level in extraction utilities
    to avoid code duplication and follow the singleton pattern.

    Returns:
        Langfuse client instance, or None if initialization fails.
    """
    return get_langfuse()


def trace_update(
    metadata: dict | None = None,
    tags: list[str] | None = None,
) -> None:
    """
    Update the current Langfuse trace with metadata and/or tags.

    Safely handles the case where Langfuse is not available.

    Args:
        metadata: Key-value pairs to add to the trace
        tags: Tags to add to the trace
    """
    client = get_langfuse()
    if client is None:
        return

    kwargs = {}
    if metadata is not None:
        kwargs["metadata"] = metadata
    if tags is not None:
        kwargs["tags"] = tags

    if kwargs:
        client.update_current_trace(**kwargs)
