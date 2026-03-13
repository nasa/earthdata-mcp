"""Tests for util.langfuse helpers."""

from unittest.mock import MagicMock

import util.langfuse as langfuse_utils


def test_trace_update_uses_mcp_session_id_when_not_provided(monkeypatch):
    """trace_update should infer session_id from FastMCP context when available."""
    mock_client = MagicMock()
    monkeypatch.setattr(langfuse_utils, "get_langfuse", lambda: mock_client)
    monkeypatch.setattr(
        langfuse_utils,
        "_resolve_session_id_from_mcp_context",
        lambda: "mcp-session-123",
    )

    langfuse_utils.trace_update(metadata={"key": "value"})

    mock_client.update_current_trace.assert_called_once_with(
        metadata={"key": "value"},
        session_id="mcp-session-123",
    )


def test_trace_update_prefers_explicit_session_id(monkeypatch):
    """Explicit session_id should override inferred MCP session context."""
    mock_client = MagicMock()
    monkeypatch.setattr(langfuse_utils, "get_langfuse", lambda: mock_client)
    monkeypatch.setattr(
        langfuse_utils,
        "_resolve_session_id_from_mcp_context",
        lambda: "mcp-session-123",
    )

    langfuse_utils.trace_update(
        tags=["collections"],
        session_id="explicit-session-456",
    )

    mock_client.update_current_trace.assert_called_once_with(
        tags=["collections"],
        session_id="explicit-session-456",
    )


def test_trace_update_noop_without_data_or_session(monkeypatch):
    """trace_update should avoid client updates when nothing can be attached."""
    mock_client = MagicMock()
    monkeypatch.setattr(langfuse_utils, "get_langfuse", lambda: mock_client)
    monkeypatch.setattr(langfuse_utils, "_resolve_session_id_from_mcp_context", lambda: None)

    langfuse_utils.trace_update()

    mock_client.update_current_trace.assert_not_called()
