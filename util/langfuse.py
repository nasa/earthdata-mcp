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


def _resolve_client_params_from_mcp_context() -> dict:
    """Resolve clientInfo from the MCP initialize handshake via FastMCP context."""
    try:
        from fastmcp.server.dependencies import get_context  # type: ignore

        ctx = get_context()
        if ctx is None:
            return {}

        client_params = getattr(getattr(ctx, "session", None), "client_params", None)
        if client_params is None:
            return {}

        client_info = getattr(client_params, "clientInfo", None)
        if client_info is None:
            return {}

        return {
            k: v
            for k, v in {
                "client_name": getattr(client_info, "name", None),
                "client_version": getattr(client_info, "version", None),
                "client_url": getattr(client_info, "websiteUrl", None),
            }.items()
            if v is not None
        }
    except Exception:
        return {}


def log_tool_call(
    tool_kwargs: dict,
    parameters: dict | None = None,
) -> None:
    """
    Emit a structured JSON log line to the Python logger (CloudWatch) for every tool
    invocation.  The record includes the full HTTP headers and body from the MCP
    request alongside the tool name, version, and parameters, giving operators complete
    request-level visibility without relying on Langfuse being available.

    Args:
        tool_kwargs: The tool registration dict (must contain 'name' and 'version').
        parameters: Dict of keyword arguments passed to the tool (caller's **kwargs).
    """
    # Allowlisted headers — excludes authorization, cookie, and other sensitive values.
    _LOGGED_HEADERS = {
        "user-agent",
        "mcp-protocol-version",
        "mcp-session-id",
        "x-forwarded-for",
        "origin",
        "referer",
        "content-type",
        "accept",
    }

    headers = {}
    client_info: dict = {}
    try:
        from fastmcp.server.dependencies import get_http_request  # type: ignore

        http_request = get_http_request()
        if http_request is not None:
            client = getattr(http_request, "client", None)
            if client is not None:
                client_info = {
                    "host": getattr(client, "host", None),
                    "port": getattr(client, "port", None),
                }

            # Use the public .headers property, not the private _headers attribute.
            headers = {
                k: v
                for k, v in http_request.headers.items()
                if k.lower() in _LOGGED_HEADERS
            }
    except Exception:
        pass

    # Merge in client_name, client_version, client_url from the MCP handshake so
    # the CloudWatch record carries the same parsed client identity that Langfuse does.
    client_params = _resolve_client_params_from_mcp_context()

    record: dict = {
        "event": "tool_call",
        "tool": tool_kwargs["name"],
        "tool_version": tool_kwargs.get("version"),
        "parameters": parameters or {},
        "client_info": client_info,
        "http_headers": headers,
        **client_params,
    }

    logger.info(json.dumps(record))


def _resolve_client_info_from_mcp_context() -> dict:
    """Resolve client host/port from the Starlette request and clientInfo from the MCP handshake."""
    info: dict = {}
    try:
        from fastmcp.server.dependencies import get_http_request  # type: ignore

        http_request = get_http_request()
        if http_request is not None:
            client = getattr(http_request, "client", None)
            if client is not None:
                host = getattr(client, "host", None)
                port = getattr(client, "port", None)
                if host is not None:
                    info["client_host"] = host
                if port is not None:
                    info["client_port"] = port

            # Prefer x-forwarded-for over client.host when behind a load balancer.
            forwarded_for = http_request.headers.get("x-forwarded-for")
            if forwarded_for:
                info["client_host"] = forwarded_for.split(",")[0].strip()
    except Exception:
        pass

    info.update(_resolve_client_params_from_mcp_context())
    return info


def get_request_metadata() -> dict:
    """
    Get metadata from the current request context for storage in Langfuse trace metadata.

    These values all go into the metadata bag — not top-level trace fields. Langfuse
    top-level fields (session_id, tags, user_id) are handled separately in trace_update
    so they are indexed and filterable in the UI. Everything here is context that is
    useful to inspect per-trace but not needed as a filter column.
    """
    metadata = {}

    mcp_protocol_version = _resolve_mcp_protocol_version_from_context()
    if mcp_protocol_version:
        metadata["mcp_protocol_version"] = mcp_protocol_version

    metadata.update(_resolve_client_info_from_mcp_context())

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
        metadata: Key-value pairs to add to the trace. Merged on top of request
            metadata when ``include_request_metadata`` is True, so callers can
            inject arbitrary keys (e.g. ``{"tool_version": "1.2.3"}``) here.
        tags: Tags to add to the trace
        session_id: Session ID to group traces together
        include_request_metadata: If True, automatically include session_id and user_agent from request context
    """
    client = get_langfuse()
    if client is None:
        return

    kwargs = {}

    # --- Langfuse top-level fields (indexed, filterable in the UI) ---
    # session_id and tags are first-class Langfuse fields; they go as top-level kwargs.
    # client_name is promoted to a tag so it appears as a filter column.
    resolved_session_id = session_id or _resolve_session_id_from_mcp_context()
    if resolved_session_id is not None:
        kwargs["session_id"] = resolved_session_id

    client_params = _resolve_client_params_from_mcp_context()
    client_name = client_params.get("client_name")
    resolved_tags = list(tags) if tags is not None else []
    if client_name and client_name not in resolved_tags:
        resolved_tags.append(client_name)
    if resolved_tags:
        kwargs["tags"] = resolved_tags

    # --- Langfuse metadata bag (inspectable per-trace, not filterable as columns) ---
    # Includes protocol version, client host/port, client name/version/url, and any
    # caller-supplied keys. Caller values are merged last so they can override.
    combined_metadata: dict = {}
    if include_request_metadata:
        combined_metadata.update(get_request_metadata())
        combined_metadata.update(client_params)
    if metadata is not None:
        combined_metadata.update(metadata)
    if combined_metadata:
        kwargs["metadata"] = combined_metadata

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
