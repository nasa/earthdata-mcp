"""Tests for the submit_request MCP tool."""

import importlib
import types
from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest


# Mock status response for when the job successfully submits
MOCK_STATUS_RESPONSE = {
    "status": "running",
    "message": "The job is being processed",
    "progress": 9,
    "created_at": "2026-09-14T03:29:36.665000+00:00",
    "updated_at": "2026-09-14T03:29:37.591000+00:00",
    "created_at_local": "2026-09-13T23:29:36-04:00",
    "updated_at_local": "2026-09-13T23:29:37-04:00",
    "request": "https://harmony.earthdata.nasa.gov/...",
    "num_input_granules": 2,
    "data_expiration": "2026-10-14T03:29:36.665000+00:00",
    "data_expiration_local": "2026-10-13T23:29:36-04:00"
}

# The job ID that client.submit() returns
MOCK_JOB_ID = "job-id-12345"


def _load_tool() -> types.ModuleType:
    """Load the tool module dynamically to avoid circular imports."""
    # Note: Adjust the import path below to match your project structure
    return importlib.import_module("tools.submit_request.tool")


@pytest.fixture
def mock_get_access_token() -> Generator[MagicMock, None, None]:
    """Mock the get_access_token function specifically within the tool module."""
    with patch("tools.submit_request.tool.get_access_token") as mock_token_func:
        mock_token_obj = MagicMock()
        mock_token_obj.token = "fake-jwt-token"
        mock_token_func.return_value = mock_token_obj
        yield mock_token_func


@pytest.fixture
def mock_get_client() -> Generator[MagicMock, None, None]:
    """Mock util.harmony.client.get_client within the tool."""
    with patch("tools.submit_request.tool.get_client") as mock_client:
        yield mock_client


@pytest.fixture
def mock_harmony_request() -> Generator[MagicMock, None, None]:
    """Mock harmony.Request to avoid triggering real harmony-py logic."""
    with patch("tools.submit_request.tool.harmony.Request") as mock_req:
        yield mock_req


@pytest.fixture
def mock_harmony_collection() -> Generator[MagicMock, None, None]:
    """Mock harmony.Collection."""
    with patch("tools.submit_request.tool.harmony.Collection") as mock_coll:
        yield mock_coll


@pytest.fixture
def mock_harmony_bbox() -> Generator[MagicMock, None, None]:
    """Mock harmony.BBox."""
    with patch("tools.submit_request.tool.harmony.BBox") as mock_bbox:
        yield mock_bbox


def test_submit_request_minimal_success(
    mock_get_client: MagicMock,
    mock_get_access_token: MagicMock,
    mock_harmony_request: MagicMock,
    mock_harmony_collection: MagicMock,
) -> None:
    """Test successful submission with only the required collection_id."""
    tool = _load_tool()

    # Arrange Mocks
    mock_client_instance = MagicMock()
    mock_get_client.return_value = mock_client_instance
    mock_client_instance.submit.return_value = MOCK_JOB_ID
    mock_client_instance.status.return_value = MOCK_STATUS_RESPONSE

    mock_req_instance = MagicMock()
    mock_harmony_request.return_value = mock_req_instance
    mock_coll_instance = MagicMock()
    mock_harmony_collection.return_value = mock_coll_instance

    # Act
    result = tool.submit_request(collection_id="C12345-PROV")

    # Assert 
    # Check that job_id was merged into the status dictionary correctly
    assert result == {"job_id": MOCK_JOB_ID, **MOCK_STATUS_RESPONSE}
    
    mock_harmony_collection.assert_called_once_with(id="C12345-PROV")
    mock_harmony_request.assert_called_once_with(collection=mock_coll_instance, labels=["harmony-mcp"])
    
    mock_get_access_token.assert_called_once()
    mock_get_client.assert_called_once_with("fake-jwt-token")
    mock_client_instance.submit.assert_called_once_with(mock_req_instance)
    mock_client_instance.status.assert_called_once_with(MOCK_JOB_ID)


def test_submit_request_all_params_success(
    mock_get_client: MagicMock,
    mock_get_access_token: MagicMock,
    mock_harmony_request: MagicMock,
    mock_harmony_collection: MagicMock,
    mock_harmony_bbox: MagicMock,
) -> None:
    """Test successful submission with all optional parameters provided."""
    tool = _load_tool()

    # Arrange Mocks
    mock_client_instance = MagicMock()
    mock_get_client.return_value = mock_client_instance
    mock_client_instance.submit.return_value = MOCK_JOB_ID
    mock_client_instance.status.return_value = MOCK_STATUS_RESPONSE

    mock_req_instance = MagicMock()
    mock_harmony_request.return_value = mock_req_instance
    mock_coll_instance = MagicMock()
    mock_harmony_collection.return_value = mock_coll_instance
    mock_bbox_instance = MagicMock()
    mock_harmony_bbox.return_value = mock_bbox_instance

    # Act
    result = tool.submit_request(
        collection_id="C12345-PROV",
        bbox=[-10.0, -20.0, 10.0, 20.0],
        shape="path/to/shape.zip",
        temporal_start="2026-01-01T00:00:00Z",
        temporal_stop="2026-12-31T23:59:59Z",
        variables=["var1", "var2"],
        format="image/tiff",
        crs="EPSG:4326",
        width=1024,
        height=2048,
        max_results=10,
        granule_ids=["G1-PROV", "G2-PROV"]
    )

    # Assert
    assert result["job_id"] == MOCK_JOB_ID
    mock_harmony_bbox.assert_called_once_with(w=-10.0, s=-20.0, e=10.0, n=20.0)

    # Verify that the harmony.Request object was built with the correct kwargs
    call_kwargs = mock_harmony_request.call_args.kwargs
    assert call_kwargs["collection"] == mock_coll_instance
    assert call_kwargs["spatial"] == mock_bbox_instance
    assert call_kwargs["shape"] == "path/to/shape.zip"
    assert call_kwargs["variables"] == ["var1", "var2"]
    assert call_kwargs["format"] == "image/tiff"
    assert call_kwargs["crs"] == "EPSG:4326"
    assert call_kwargs["width"] == 1024
    assert call_kwargs["height"] == 2048
    assert call_kwargs["max_results"] == 10
    assert call_kwargs["granule_id"] == ["G1-PROV", "G2-PROV"]
    assert call_kwargs["labels"] == ["harmony-mcp"]
    
    # Ensure temporal parsed the strings into datetime objects
    assert "start" in call_kwargs["temporal"]
    assert "stop" in call_kwargs["temporal"]


def test_submit_request_invalid_bbox_length() -> None:
    """Test explicitly checking for bbox validation."""
    tool = _load_tool()

    # Pass only 3 values instead of 4
    result = tool.submit_request(collection_id="C12345-PROV", bbox=[-10.0, -20.0, 10.0])

    assert result.get("code") == "ValueError"
    assert "bbox must have exactly 4 values" in result.get("description", "")


def test_submit_request_invalid_temporal_date() -> None:
    """Test explicitly checking for dateutil parsing errors."""
    tool = _load_tool()

    # Pass garbage date string
    result = tool.submit_request(collection_id="C12345-PROV", temporal_start="not-a-real-date")

    assert result.get("code") == "ParserError"
    assert "Invalid date format" in result.get("description", "")


def test_submit_request_missing_collection_id() -> None:
    """Test behavior when input validation fails due to missing required parameter."""
    tool = _load_tool()

    # Act
    result = tool.submit_request(collection_id=None)

    # Assert
    assert result.get("code") in ["ValueError", "ValidationError"]
    assert "collection_id" in result.get("description", "").lower()


def test_submit_request_client_error(
    mock_get_client: MagicMock,
    mock_get_access_token: MagicMock,
    mock_harmony_request: MagicMock,
    mock_harmony_collection: MagicMock,
) -> None:
    """Test behavior when the Harmony API client raises an exception."""
    tool = _load_tool()

    mock_client_instance = MagicMock()
    mock_get_client.return_value = mock_client_instance
    
    # Simulate an error from the Harmony API during submit
    mock_client_instance.submit.side_effect = Exception("Service Unavailable")

    # Act
    result = tool.submit_request(collection_id="C12345-PROV")
    
    # Assert
    assert result.get("code") == "Exception"
    assert "Failed to submit request to Harmony: Service Unavailable" in result.get("description", "")


def test_submit_request_calls_trace_update(
    mock_get_client: MagicMock,
    mock_get_access_token: MagicMock,
    mock_harmony_request: MagicMock,
    mock_harmony_collection: MagicMock,
) -> None:
    """Test telemetry tracing is called correctly."""
    tool = _load_tool()
    
    mock_client_instance = MagicMock()
    mock_get_client.return_value = mock_client_instance
    mock_client_instance.submit.return_value = MOCK_JOB_ID
    mock_client_instance.status.return_value = {}

    with patch.object(tool, "trace_update") as mock_trace_update:
        tool.submit_request(collection_id="C123")

    assert mock_trace_update.called