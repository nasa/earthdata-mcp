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
    except Exception as e:
        logger.debug("Failed to flush Langfuse: %s", e)


def initialize_langfuse_client() -> Langfuse | None:
    """
    Initialize module-level Langfuse client for use in utility modules.

    This function is designed to be called at module level in extraction utilities
    to avoid code duplication and follow the singleton pattern.

    Returns:
        Langfuse client instance, or None if initialization fails.
    """
    return get_langfuse()


def _resolve_session_id_from_mcp_context() -> str | None:
    """Resolve session id from FastMCP request context when available."""
    try:
        # Import lazily so this utility also works in non-FastMCP runtimes.
        from fastmcp.server.dependencies import get_context  # type: ignore

        ctx = get_context()
        if ctx is None:
            return None

        session_id = getattr(ctx, "session_id", None)
        return session_id if isinstance(session_id, str) and session_id else None
    except Exception:
        # Outside request context (or FastMCP not available), no session can be inferred.
        return None


def trace_update(
    metadata: dict | None = None,
    tags: list[str] | None = None,
    session_id: str | None = None,
) -> None:
    """
    Update the current Langfuse trace with metadata and/or tags.

    Safely handles the case where Langfuse is not available.

    Args:
        metadata: Key-value pairs to add to the trace
        tags: Tags to add to the trace
        session_id: Session ID to group traces together
    """
    client = get_langfuse()
    if client is None:
        return

    kwargs = {}
    if metadata is not None:
        kwargs["metadata"] = metadata
    if tags is not None:
        kwargs["tags"] = tags
    resolved_session_id = session_id or _resolve_session_id_from_mcp_context()
    if resolved_session_id is not None:
        kwargs["session_id"] = resolved_session_id

    if kwargs:
        client.update_current_trace(**kwargs)


def get_current_trace_id() -> str | None:
    """
    Get the current trace ID from the Langfuse context.

    This is useful for attaching scores to the current trace created by @observe decorator.

    Returns:
        Current trace ID, or None if not in a trace context or Langfuse is unavailable.
    """
    try:
        from langfuse.decorators import langfuse_context

        return langfuse_context.get_current_trace_id()
    except Exception as e:
        logger.warning("Failed to get current trace ID: %s", e)
        return None


def create_score(
    name: str,
    value: float,
    comment: str = "",
    data_type: str = "NUMERIC",
    trace_id: str | None = None,
) -> None:
    """
    Create a score for the current trace.

    If trace_id is not provided, will attempt to get the current trace ID from context.
    Safely handles cases where Langfuse is unavailable or not in a trace context.

    Args:
        name: Name of the metric/score
        value: Numeric value of the score
        comment: Optional comment/explanation for the score
        data_type: Type of data ("NUMERIC", "CATEGORICAL", "BOOLEAN")
        trace_id: Optional trace ID. If None, uses current trace from context.
    """
    try:
        # Get trace ID if not provided
        if trace_id is None:
            trace_id = get_current_trace_id()

        if trace_id is None:
            logger.warning("No trace ID available for creating score: %s", name)
            return

        # Get Langfuse client
        langfuse = get_langfuse()
        if langfuse is None:
            return

        # Create the score
        langfuse.create_score(
            name=name,
            value=value,
            trace_id=trace_id,
            data_type=data_type,
            comment=comment,
        )
    except Exception as e:
        logger.warning("Failed to create score '%s': %s", name, e)
