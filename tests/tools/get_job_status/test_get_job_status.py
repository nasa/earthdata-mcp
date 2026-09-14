"""Tests for the get_job_status MCP tool."""

import importlib
import types
from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest


# Mock payload based on the Harmony API response
MOCK_STATUS_RESPONSE = {
    "status": "successful",
    "message": "The job has completed successfully",
    "progress": 100,
    "created_at": "2026-08-03T21:52:28.600000+00:00",
    "updated_at": "2026-08-03T22:16:33.498000+00:00",
    "created_at_local": "2026-08-03T17:52:28-04:00",
    "updated_at_local": "2026-08-03T18:16:33-04:00",
    "request": "https://harmony.earthdata.nasa.gov/...",
    "num_input_granules": 2000,
    "data_expiration": "2026-09-02T21:52:28.600000+00:00",
    "data_expiration_local": "2026-09-02T17:52:28-04:00"
}


def _load_tool() -> types.ModuleType:
    """Load the tool module dynamically to avoid circular imports."""
    # Note: Adjust the import path below to match your project structure
    return importlib.import_module("tools.get_job_status.tool")


@pytest.fixture
def mock_get_access_token() -> Generator[MagicMock, None, None]:
    """Mock the get_access_token function specifically within the tool module."""
    with patch("tools.get_job_status.tool.get_access_token") as mock_token_func:
        mock_token_obj = MagicMock()
        mock_token_obj.token = "fake-jwt-token"
        mock_token_func.return_value = mock_token_obj
        yield mock_token_func


@pytest.fixture
def mock_get_client() -> Generator[MagicMock, None, None]:
    """Mock util.harmony.client.get_client within the tool."""
    with patch("tools.get_job_status.tool.get_client") as mock_client:
        yield mock_client


def test_get_job_status_success(
    mock_get_client: MagicMock,
    mock_get_access_token: MagicMock
) -> None:
    """Test successful retrieval of job status."""
    tool = _load_tool()

    # Arrange mocks
    mock_client_instance = MagicMock()
    mock_get_client.return_value = mock_client_instance
    mock_client_instance.status.return_value = MOCK_STATUS_RESPONSE

    # Act
    job_id = "test-job-12345"
    result = tool.get_job_status(job_id=job_id)

    # Assert
    assert result == MOCK_STATUS_RESPONSE
    mock_get_access_token.assert_called_once()
    mock_get_client.assert_called_once_with("fake-jwt-token")
    mock_client_instance.status.assert_called_once_with(job_id)


def test_get_job_status_calls_trace_update(
    mock_get_client: MagicMock,
    mock_get_access_token: MagicMock
) -> None:
    """Test telemetry tracing is called correctly."""
    tool = _load_tool()
    
    mock_client_instance = MagicMock()
    mock_get_client.return_value = mock_client_instance
    mock_client_instance.status.return_value = {}

    with patch.object(tool, "trace_update") as mock_trace_update:
        tool.get_job_status(job_id="test-job")

    assert mock_trace_update.called


def test_get_job_status_validation_error() -> None:
    """Test behavior when input validation fails (e.g., job_id is missing/None)."""
    tool = _load_tool()

    # Act
    result = tool.get_job_status(job_id=None)

    # Assert
    assert result.get("code") in ["ValueError", "ValidationError"]
    assert "job_id" in result.get("description", "").lower()


def test_get_job_status_client_error(
    mock_get_client: MagicMock,
    mock_get_access_token: MagicMock
) -> None:
    """Test behavior when the Harmony API client raises an exception."""
    tool = _load_tool()

    # Arrange mocks
    mock_client_instance = MagicMock()
    mock_get_client.return_value = mock_client_instance
    
    # Simulate an error from the Harmony API (e.g., Job not found or Unauthorized)
    mock_client_instance.status.side_effect = Exception("Job test-job-123 not found")

    # Act
    result = tool.get_job_status(job_id="test-job-123")
    
    # Assert
    assert result.get("code") == "Exception"
    assert "Failed to fetch job status from Harmony: Job test-job-123 not found" in result.get("description", "")