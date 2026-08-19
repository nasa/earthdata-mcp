"""Langfuse client utility."""

import logging
import os
import json
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


def _resolve_header_from_mcp_context(header_name: str) -> str | None:
    """Resolve a header value from the FastMCP HTTP request context when available."""
    try:
        # Import lazily so this utility also works in non-FastMCP runtimes.
        from fastmcp.server.dependencies import get_http_request  # type: ignore

        http_request = get_http_request()
        if http_request is None:
            return None

        value = http_request.headers.get(header_name)
        return value if isinstance(value, str) and value else None
    except Exception:
        # Outside request context or headers not available
        return None


def _resolve_user_agent_from_mcp_context() -> str | None:
    """Resolve user-agent from FastMCP request context when available."""
    return _resolve_header_from_mcp_context("user-agent")


def _resolve_mcp_protocol_version_from_context() -> str | None:
    """Resolve mcp-protocol-version from FastMCP request context when available."""
    return _resolve_header_from_mcp_context("mcp-protocol-version")


def log_tool_call(tool_name: str, parameters: dict | None = None) -> None:
    """
    Emit a structured JSON log line to the Python logger (CloudWatch) for every tool
    invocation.  The record includes the full HTTP headers and body from the MCP
    request alongside the tool name and parameters, giving operators complete
    request-level visibility without relying on Langfuse being available.

    Args:
        tool_name: Name of the MCP tool being invoked.
        parameters: Dict of keyword arguments passed to the tool (caller's **kwargs).
    """
    headers = {}
    body = {}
    try:
        from fastmcp.server.dependencies import get_http_request  # type: ignore

        http_request = get_http_request()
        if http_request is not None:
            raw_headers = getattr(http_request, "_headers", None)
            if raw_headers is not None:
                # Starlette stores headers as a list of (name, value) byte tuples.
                headers = {
                    k.decode() if isinstance(k, bytes) else k: (
                        v.decode() if isinstance(v, bytes) else v
                    )
                    for k, v in (
                        raw_headers.items() if hasattr(raw_headers, "items") else []
                    )
                }

            raw_body = getattr(http_request, "_body", None)
            if raw_body is not None:
                # 1. Decode to a string safely first
                body_str = (
                    raw_body.decode("utf-8", errors="ignore")
                    if isinstance(raw_body, bytes)
                    else (raw_body or "")
                )

                # 2. Attempt to parse it as JSON
                try:
                    # strip() removes leading/trailing spaces or newlines that cause parse errors
                    body = json.loads(body_str.strip()) if body_str.strip() else {}
                except (json.JSONDecodeError, AttributeError):
                    # Fallback to an empty dict or a standard format if it isn't valid JSON
                    body = {"raw_text": body_str} if body_str else {}
    except Exception:
        pass

    record: dict = {
        "event": "tool_call",
        "tool": tool_name,
        "parameters": parameters or {},
        "http_headers": headers,
        "http_body": body,
    }

    logger.info(json.dumps(record))


def get_request_metadata() -> dict:
    """Get metadata from the current request context (session_id, user_agent, etc.)."""
    metadata = {}

    session_id = _resolve_session_id_from_mcp_context()
    if session_id:
        metadata["session_id"] = session_id

    user_agent = _resolve_user_agent_from_mcp_context()
    metadata["user_agent"] = user_agent if user_agent else "Unknown"

    mcp_protocol_version = _resolve_mcp_protocol_version_from_context()
    if mcp_protocol_version:
        metadata["mcp_protocol_version"] = mcp_protocol_version

    return metadata


def trace_update(
    metadata: dict | None = None,
    tags: list[str] | None = None,
    session_id: str | None = None,
    include_request_metadata: bool = True,
) -> None:
    """
    Update the current Langfuse trace with metadata and/or tags.

    Safely handles the case where Langfuse is not available.

    Args:
        metadata: Key-value pairs to add to the trace
        tags: Tags to add to the trace
        session_id: Session ID to group traces together
        include_request_metadata: If True, automatically include session_id and user_agent from request context
    """
    client = get_langfuse()
    if client is None:
        return

    kwargs = {}

    # Build metadata, optionally including request context
    combined_metadata = {}
    if include_request_metadata:
        combined_metadata.update(get_request_metadata())
    if metadata is not None:
        combined_metadata.update(metadata)

    if combined_metadata:
        kwargs["metadata"] = combined_metadata

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
