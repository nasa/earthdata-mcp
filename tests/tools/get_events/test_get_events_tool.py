"""Tests for the get_events MCP tool."""

import importlib
import types
from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
import requests

from models.tools.cmr_search import SearchStatus


def _load_tool() -> types.ModuleType:
    """Load the tool module dynamically to avoid circular imports."""
    return importlib.import_module("tools.get_events.tool")


@pytest.fixture
def mock_requests_get() -> Generator[MagicMock]:
    """Mock requests.get."""
    with patch("tools.get_events.tool.requests.get") as mock_get:
        yield mock_get


def test_get_events_success(mock_requests_get: MagicMock) -> None:
    """Test successful retrieval of EONET events."""
    tool = _load_tool()

    mock_requests_get.return_value = [
        {
            "id": "EONET_123",
            "title": "Wildfire in Region X",
            "metadata": {"source": "NASA"},
            "description": "A large wildfire observed."
        }
    ]

    result = tool.get_events(endpoint="/v3/events", event_params={})

    assert result["status"] == SearchStatus.SUCCESS
    assert result["total_hits"] == 1
    assert len(result["events"]) == 1
    assert result["events"][0]["id"] == "EONET_123"
    assert result["events"][0]["title"] == "Wildfire in Region X"
    assert result["events"][0]["metadata"]["source"] == "NASA"
    assert result["events"][0]["description"] == "A large wildfire observed."


def test_get_events_empty_endpoint() -> None:
    """Test behavior when an empty endpoint is provided (triggers specific if/else branch)."""
    tool = _load_tool()

    result = tool.get_events(endpoint="")

    assert result["status"] == SearchStatus.ERROR
    assert result["total_hits"] == 0
    assert len(result["events"]) == 0
    assert "Endpoint cannot be empty." in result["error_message"]


def test_get_events_api_error(mock_requests_get: MagicMock) -> None:
    """Test behavior when the EONET API throws a RequestException."""
    tool = _load_tool()

    mock_requests_get.side_effect = requests.RequestException("Connection Timeout")

    result = tool.get_events(endpoint="events")

    assert result["status"] == SearchStatus.ERROR
    assert result["total_hits"] == 0
    assert len(result["events"]) == 0
    assert "EONET could not process the request" in result["error_message"]


def test_get_events_no_results(mock_requests_get: MagicMock) -> None:
    """Test behavior when the EONET API returns an empty array."""
    tool = _load_tool()

    mock_response = MagicMock()
    mock_response.json.return_value = []
    mock_requests_get.return_value = mock_response

    result = tool.get_events(endpoint="events")

    assert result["status"] == SearchStatus.NO_RESULTS
    assert result["total_hits"] == 0
    assert len(result["events"]) == 0
    assert result["error_message"] is None


def test_get_events_input_validation_error() -> None:
    """Test behavior when inputs fail the Pydantic GetEventsInput validation."""
    tool = _load_tool()
    
    # Passing an intentionally bad type (e.g., a dictionary for a string endpoint or limit)
    # The exact inputs here depend on what triggers a ValueError or TypeError in your Pydantic model
    result = tool.get_events(endpoint={"bad": "type"}, limit="not_an_integer")

    assert result["status"] == SearchStatus.ERROR
    assert result["total_hits"] == 0
    assert result["error_message"] is not None