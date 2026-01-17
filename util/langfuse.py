"""Langfuse client utility."""

import logging
import os

from langfuse import Langfuse

from util.ssm import get_parameter

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
        secret_key = None
        ssm_parameter = os.environ.get("LANGFUSE_SECRET_KEY_SSM_PARAMETER")
        if ssm_parameter:
            secret_key = get_parameter(ssm_parameter)

        _langfuse_client = Langfuse(secret_key=secret_key) if secret_key else Langfuse()
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
