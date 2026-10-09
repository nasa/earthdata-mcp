"""Tests for the control_transformation_job MCP tool."""

import importlib
import types
from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from fastmcp.exceptions import ToolError

from models.tools.get_transformation_job_status import GetTransformationJobStatusOutput


# Mock status response returned by client.status() after a control action.
MOCK_STATUS_RESPONSE = {
    "code": None,
    "description": None,
    "status": "canceled",
    "message": "The job has been canceled",
    "progress": 42,
    "created_at": "2026-09-14T03:29:36.665000Z",
    "updated_at": "2026-09-17T10:00:00.000000Z",
    "request": "https://harmony.earthdata.nasa.gov/...",
    "num_input_granules": 2,
    "job_id": "job-id-12345",
    "data_expiration": "2026-10-14T03:29:36.665000Z",
    "links": [],
}

MOCK_JOB_ID = "job-id-12345"


def _load_tool() -> types.ModuleType:
    """Load the tool module dynamically to avoid circular imports."""
    return importlib.import_module("tools.control_transformation_job.tool")


@pytest.fixture
def mock_get_access_token() -> Generator[MagicMock, None, None]:
    """Mock the get_access_token function specifically within the tool module."""
    with patch("tools.control_transformation_job.tool.get_access_token") as mock_token_func:
        mock_token_obj = MagicMock()
        mock_token_obj.token = "fake-jwt-token"
        mock_token_func.return_value = mock_token_obj
        yield mock_token_func


@pytest.fixture
def mock_get_client() -> Generator[MagicMock, None, None]:
    """Mock util.harmony.client.get_client within the tool."""
    with patch("tools.control_transformation_job.tool.get_client") as mock_client:
        yield mock_client


@pytest.mark.parametrize("action", ["cancel", "pause", "resume"])
def test_control_transformation_job_action_success(
    action: str,
    mock_get_client: MagicMock,
    mock_get_access_token: MagicMock,
) -> None:
    """Test that each supported action calls the correct client method and returns status."""
    tool = _load_tool()

    # Arrange mocks
    mock_client_instance = MagicMock()
    mock_get_client.return_value = mock_client_instance
    mock_client_instance.status.return_value = MOCK_STATUS_RESPONSE

    # Act
    result = tool.control_transformation_job(job_id=MOCK_JOB_ID, action=action)

    # Build expected output via the same transformation the tool performs.
    expected_output = GetTransformationJobStatusOutput(**MOCK_STATUS_RESPONSE)
    expected_output.job_id = MOCK_JOB_ID
    expected = expected_output.model_dump(mode="json", by_alias=True)

    # Assert
    assert result == expected

    mock_get_access_token.assert_called_once()
    mock_get_client.assert_called_once_with("fake-jwt-token")

    # Only the method matching the requested action should have been called.
    for candidate_action in ("cancel", "pause", "resume"):
        client_method = getattr(mock_client_instance, candidate_action)
        if candidate_action == action:
            client_method.assert_called_once_with(MOCK_JOB_ID)
        else:
            client_method.assert_not_called()

    mock_client_instance.status.assert_called_once_with(MOCK_JOB_ID)


def test_control_transformation_job_invalid_action() -> None:
    """Test behavior when an unsupported action string is passed.

    action is typed as Literal["cancel", "pause", "resume"] on the function
    signature, but Python doesn't enforce Literal types at runtime -- the
    actual rejection happens via ControlTransformationJobInput validation.
    """
    tool = _load_tool()

    with pytest.raises(ToolError) as exc_info:
        tool.control_transformation_job(job_id=MOCK_JOB_ID, action="delete")

    message = str(exc_info.value).lower()
    assert "control_transformation_job" in message
    assert "action" in message


def test_control_transformation_job_missing_job_id() -> None:
    """Test behavior when input validation fails due to missing required job_id."""
    tool = _load_tool()

    with pytest.raises(ToolError) as exc_info:
        tool.control_transformation_job(job_id=None, action="cancel")

    message = str(exc_info.value).lower()
    assert "control_transformation_job" in message
    assert "job_id" in message


def test_control_transformation_job_client_error(
    mock_get_client: MagicMock,
    mock_get_access_token: MagicMock,
) -> None:
    """Test behavior when the Harmony API client raises an exception during the action."""
    tool = _load_tool()

    mock_client_instance = MagicMock()
    mock_get_client.return_value = mock_client_instance

    # Simulate an error from Harmony during the control action itself
    # (e.g., invalid state transition, job not found, etc.)
    mock_client_instance.cancel.side_effect = Exception("Job is already in a terminal state")

    with pytest.raises(ToolError) as exc_info:
        tool.control_transformation_job(job_id=MOCK_JOB_ID, action="cancel")

    assert str(exc_info.value) == (
        "control_transformation_job Exception: Job is already in a terminal state"
    )


def test_control_transformation_job_status_fetch_error(
    mock_get_client: MagicMock,
    mock_get_access_token: MagicMock,
) -> None:
    """Test behavior when the action succeeds but the follow-up status call fails."""
    tool = _load_tool()

    mock_client_instance = MagicMock()
    mock_get_client.return_value = mock_client_instance
    mock_client_instance.status.side_effect = Exception("Service Unavailable")

    with pytest.raises(ToolError) as exc_info:
        tool.control_transformation_job(job_id=MOCK_JOB_ID, action="pause")

    mock_client_instance.pause.assert_called_once_with(MOCK_JOB_ID)
    assert str(exc_info.value) == "control_transformation_job Exception: Service Unavailable"


def test_control_transformation_job_status_schema_mismatch(
    mock_get_client: MagicMock,
    mock_get_access_token: MagicMock,
) -> None:
    """Test behavior when the action succeeds but the status response doesn't
    match the expected output schema (e.g. malformed field from Harmony)."""
    tool = _load_tool()

    mock_client_instance = MagicMock()
    mock_get_client.return_value = mock_client_instance
    # progress is typed as int | float | None -- an unparseable string causes
    # GetTransformationJobStatusOutput(**status) to raise a Pydantic
    # ValidationError (a subclass of ValueError in Pydantic v2, so it's caught
    # by the tool's `except (ValueError, TypeError)` block).
    mock_client_instance.status.return_value = {"progress": "not-a-number"}

    with pytest.raises(ToolError) as exc_info:
        tool.control_transformation_job(job_id=MOCK_JOB_ID, action="cancel")

    mock_client_instance.cancel.assert_called_once_with(MOCK_JOB_ID)
    message = str(exc_info.value)
    assert message.startswith("control_transformation_job ValidationError:")


def test_control_transformation_job_calls_trace_update(
    mock_get_client: MagicMock,
    mock_get_access_token: MagicMock,
) -> None:
    """Test telemetry tracing is called correctly."""
    tool = _load_tool()

    mock_client_instance = MagicMock()
    mock_get_client.return_value = mock_client_instance
    mock_client_instance.status.return_value = {}

    with patch.object(tool, "trace_update") as mock_trace_update:
        tool.control_transformation_job(job_id=MOCK_JOB_ID, action="resume")

    assert mock_trace_update.called
