"""Tests for util.langfuse."""

import os
from unittest.mock import MagicMock, patch

import pytest

import util.langfuse
from util.langfuse import (
    _configure_langfuse,
    _resolve_session_id_from_mcp_context,
    create_score,
    flush_langfuse,
    get_current_trace_id,
    get_langfuse,
    initialize_langfuse_client,
    trace_update,
)


@pytest.fixture(autouse=True)
def reset_langfuse_state():
    """Test fixture."""
    util.langfuse._initialized = False
    if "LANGFUSE_SECRET_KEY" in os.environ:
        del os.environ["LANGFUSE_SECRET_KEY"]
    if "ENVIRONMENT_NAME" in os.environ:
        del os.environ["ENVIRONMENT_NAME"]
    yield
    util.langfuse._initialized = False


def test_configure_langfuse_no_env():
    """Test function."""
    _configure_langfuse()
    assert util.langfuse._initialized is True
    assert "LANGFUSE_SECRET_KEY" not in os.environ


def test_configure_langfuse_with_env_and_ssm():
    """Test function."""
    os.environ["ENVIRONMENT_NAME"] = "test"
    with patch("util.langfuse.get_parameter", return_value="secret-123") as mock_get_param:
        _configure_langfuse()
        assert os.environ["LANGFUSE_SECRET_KEY"] == "secret-123"
        mock_get_param.assert_called_once_with("test-langfuse-secret-key")
        assert util.langfuse._initialized is True


def test_configure_langfuse_already_initialized():
    """Test function."""
    util.langfuse._initialized = True
    with patch("util.langfuse.get_parameter") as mock_get_param:
        _configure_langfuse()
        mock_get_param.assert_not_called()


def test_configure_langfuse_exception():
    """Test function."""
    os.environ["ENVIRONMENT_NAME"] = "test"
    with (
        patch("util.langfuse.get_parameter", side_effect=Exception("error")),
        patch("util.langfuse.logger") as mock_logger,
    ):
        _configure_langfuse()
        mock_logger.warning.assert_called_once()
        assert util.langfuse._initialized is True


def test_get_langfuse_success():
    """Test function."""
    with (
        patch("util.langfuse.get_client") as mock_get_client,
        patch("util.langfuse._configure_langfuse"),
    ):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        assert get_langfuse() is mock_client


def test_get_langfuse_exception():
    """Test function."""
    with (
        patch("util.langfuse.get_client", side_effect=Exception("error")),
        patch("util.langfuse.logger") as mock_logger,
    ):
        assert get_langfuse() is None
        mock_logger.warning.assert_called_once()


def test_flush_langfuse():
    """Test function."""
    with patch("util.langfuse.get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        flush_langfuse()
        mock_client.flush.assert_called_once()


def test_flush_langfuse_exception():
    """Test function."""
    with (
        patch("util.langfuse.get_client") as mock_get_client,
        patch("util.langfuse.logger") as mock_logger,
    ):
        mock_client = MagicMock()
        mock_client.flush.side_effect = Exception("error")
        mock_get_client.return_value = mock_client
        flush_langfuse()
        mock_logger.debug.assert_called_once()


def test_initialize_langfuse_client():
    """Test function."""
    with patch("util.langfuse.get_langfuse") as mock_get_langfuse:
        mock_client = MagicMock()
        mock_get_langfuse.return_value = mock_client
        assert initialize_langfuse_client() is mock_client


def test_resolve_session_id_from_mcp_context_success():
    """Test function."""
    mock_ctx = MagicMock()
    mock_ctx.session_id = "sess-123"
    with patch.dict(
        "sys.modules",
        {"fastmcp.server.dependencies": MagicMock(get_context=MagicMock(return_value=mock_ctx))},
    ):
        assert _resolve_session_id_from_mcp_context() == "sess-123"


def test_resolve_session_id_from_mcp_context_none():
    """Test function."""
    with patch.dict(
        "sys.modules",
        {"fastmcp.server.dependencies": MagicMock(get_context=MagicMock(return_value=None))},
    ):
        assert _resolve_session_id_from_mcp_context() is None


def test_resolve_session_id_from_mcp_context_exception():
    """Test function."""
    assert _resolve_session_id_from_mcp_context() is None


def test_trace_update_with_client():
    """Test function."""
    with (
        patch("util.langfuse.get_langfuse") as mock_get_langfuse,
        patch("util.langfuse._resolve_session_id_from_mcp_context", return_value="sess-123"),
    ):
        mock_client = MagicMock()
        mock_get_langfuse.return_value = mock_client
        trace_update(metadata={"a": 1}, tags=["tag1"], session_id=None)
        mock_client.update_current_trace.assert_called_once_with(
            metadata={"a": 1}, tags=["tag1"], session_id="sess-123"
        )


def test_get_current_trace_id_success():
    """Test function."""
    with patch.dict(
        "sys.modules",
        {
            "langfuse.decorators": MagicMock(
                langfuse_context=MagicMock(get_current_trace_id=MagicMock(return_value="trace-123"))
            )
        },
    ):
        assert get_current_trace_id() == "trace-123"


def test_get_current_trace_id_exception():
    """Test function."""
    with patch("util.langfuse.logger") as mock_logger:
        assert get_current_trace_id() is None
        mock_logger.warning.assert_called_once()


def test_create_score():
    """Test function."""
    with (
        patch("util.langfuse.get_current_trace_id", return_value="trace-123"),
        patch("util.langfuse.get_langfuse") as mock_get_langfuse,
    ):
        mock_client = MagicMock()
        mock_get_langfuse.return_value = mock_client
        create_score(name="accuracy", value=1.0)
        mock_client.create_score.assert_called_once_with(
            name="accuracy", value=1.0, trace_id="trace-123", data_type="NUMERIC", comment=""
        )


def test_create_score_no_trace_id():
    """Test function."""
    with (
        patch("util.langfuse.get_current_trace_id", return_value=None),
        patch("util.langfuse.logger") as mock_logger,
    ):
        create_score(name="accuracy", value=1.0)
        mock_logger.warning.assert_called_once()


def test_create_score_no_client():
    """Test function."""
    with (
        patch("util.langfuse.get_current_trace_id", return_value="trace-123"),
        patch("util.langfuse.get_langfuse", return_value=None),
    ):
        create_score(name="accuracy", value=1.0)


def test_create_score_exception():
    """Test function."""
    with (
        patch("util.langfuse.get_current_trace_id", return_value="trace-123"),
        patch("util.langfuse.get_langfuse") as mock_get_langfuse,
        patch("util.langfuse.logger") as mock_logger,
    ):
        mock_client = MagicMock()
        mock_client.create_score.side_effect = Exception("error")
        mock_get_langfuse.return_value = mock_client
        create_score(name="accuracy", value=1.0)
        mock_logger.warning.assert_called_once()
