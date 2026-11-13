"""Tests for the get_events MCP tool."""

import importlib
import types
from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from fastmcp.exceptions import ToolError

from models.tools.cmr_search import SearchStatus
from util.eonet.client import (
    EONETError,
)


def _load_tool() -> types.ModuleType:
    """Load the tool module dynamically to avoid circular imports."""
    return importlib.import_module("tools.get_events.tool")


@pytest.fixture
def mock_events_endpoint() -> Generator[MagicMock]:
    """Mock tools.get_events.tool.events."""
    with patch("tools.get_events.tool.events") as mock_events:
        yield mock_events


TEST_PARAMS = {
    "source": None,
    "category": None,
    "status": "all",
    "limit": 5,
    "days": None,
    "start": None,
    "end": None,
    "magID": None,
    "magMin": None,
    "magMax": None,
    "bbox": None,
}


def _reset_test_params():
    global TEST_PARAMS
    TEST_PARAMS = {
        "source": None,
        "category": None,
        "status": "all",
        "limit": 5,
        "days": None,
        "start": None,
        "end": None,
        "magID": None,
        "magMin": None,
        "magMax": None,
        "bbox": None,
    }


def test_get_events_returns_event(mock_events_endpoint: MagicMock) -> None:
    """Test that get_events can return 1 result successfully."""
    tool = _load_tool()

    mock_events_endpoint.return_value = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [0.0, 0.0]},
                "properties": {"name": "A Cool Place", "location": "Anytown, USA"},
            }
        ],
    }

    expected = {
        "status": SearchStatus.SUCCESS,
        "error_message": None,
        "data": {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [0.0, 0.0]},
                    "properties": {"name": "A Cool Place", "location": "Anytown, USA"},
                }
            ],
        },
    }

    TEST_PARAMS["limit"] = 1

    result = tool.get_events(**TEST_PARAMS)

    assert result["status"] == expected["status"]
    assert result["error_message"] == expected["error_message"]
    assert result["data"] == expected["data"]
    mock_events_endpoint.assert_called_once_with(TEST_PARAMS, True)

    _reset_test_params()


def test_get_events_returns_multiple_events(mock_events_endpoint: MagicMock) -> None:
    """Test that get_events can return multiple results successfully."""
    tool = _load_tool()

    mock_events_endpoint.return_value = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [0.0, 0.0]},
                "properties": {"name": "A Cool Place", "location": "Anytown, USA"},
            },
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [1.0, 1.0]},
                "properties": {"name": "Another Cool Place", "location": "Anothertown, USA"},
            },
        ],
    }

    expected = {
        "status": SearchStatus.SUCCESS,
        "error_message": None,
        "data": {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [0.0, 0.0]},
                    "properties": {"name": "A Cool Place", "location": "Anytown, USA"},
                },
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [1.0, 1.0]},
                    "properties": {"name": "Another Cool Place", "location": "Anothertown, USA"},
                },
            ],
        },
    }

    TEST_PARAMS["limit"] = 2

    result = tool.get_events(**TEST_PARAMS)

    assert result["status"] == expected["status"]
    assert result["error_message"] == expected["error_message"]
    assert result["data"] == expected["data"]
    mock_events_endpoint.assert_called_once_with(TEST_PARAMS, True)

    _reset_test_params()


def test_get_events_returns_no_events(mock_events_endpoint: MagicMock) -> None:
    """Test that get_events can return no results successfully."""
    tool = _load_tool()

    mock_events_endpoint.return_value = {
        "type": "FeatureCollection",
        "features": [],
    }

    expected = {
        "status": SearchStatus.NO_RESULTS,
        "error_message": None,
        "data": {},
    }

    TEST_PARAMS["limit"] = 1

    result = tool.get_events(**TEST_PARAMS)

    assert result["status"] == expected["status"]
    assert result["error_message"] == expected["error_message"]
    assert result["data"] == expected["data"]
    mock_events_endpoint.assert_called_once_with(TEST_PARAMS, True)

    _reset_test_params()


def test_get_events_does_not_post_filter_api_response(mock_events_endpoint: MagicMock) -> None:
    """Test that get_events returns whatever features the API returns without post-filtering."""
    tool = _load_tool()

    mock_events_endpoint.return_value = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [0.0, 0.0]},
                "properties": {"name": "A Cool Place", "location": "Anytown, USA"},
            },
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [1.0, 1.0]},
                "properties": {"name": "Another Cool Place", "location": "Anothertown, USA"},
            },
        ],
    }

    expected = {
        "status": SearchStatus.SUCCESS,
        "error_message": None,
        "data": {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [0.0, 0.0]},
                    "properties": {"name": "A Cool Place", "location": "Anytown, USA"},
                },
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [1.0, 1.0]},
                    "properties": {"name": "Another Cool Place", "location": "Anothertown, USA"},
                },
            ],
        },
    }

    TEST_PARAMS["limit"] = 2

    result = tool.get_events(**TEST_PARAMS)

    assert result["status"] == expected["status"]
    assert result["error_message"] == expected["error_message"]
    assert result["data"] == expected["data"]
    mock_events_endpoint.assert_called_once_with(TEST_PARAMS, True)

    _reset_test_params()


def test_get_events_returns_error_for_invalid_input() -> None:
    """Test that get_events returns an error if invalid input is passed to params."""
    tool = _load_tool()

    TEST_PARAMS["source"] = 123

    with pytest.raises(ToolError) as e:
        tool.get_events(**TEST_PARAMS)

    assert "get_events ValidationError" in str(e)

    _reset_test_params()


def test_get_events_returns_error_for_bad_eonet_connection(mock_events_endpoint: MagicMock) -> None:
    """Test that get_events returns an error if it can't reach the EONET API."""
    tool = _load_tool()

    mock_events_endpoint.side_effect = EONETError("Failed to fetch events from EONET")

    TEST_PARAMS["limit"] = 1

    with pytest.raises(ToolError) as e:
        tool.get_events(**TEST_PARAMS)

    assert "Failed to fetch events from EONET" in str(e)

    _reset_test_params()


def test_get_events_returns_error_for_malformed_event_results(
    mock_events_endpoint: MagicMock,
) -> None:
    """Test that get_events returns an error if results are malformed."""
    tool = _load_tool()

    mock_events_endpoint.return_value = {}

    mock_events_endpoint.side_effect = EONETError(
        "Unexpected response shape: 'features' and/or 'type' keys missing."
    )

    TEST_PARAMS["limit"] = 1

    with pytest.raises(ToolError) as e:
        tool.get_events(**TEST_PARAMS)

    assert "Unexpected response shape: 'features' and/or 'type' keys missing." in str(e)

    _reset_test_params()


def test_get_events_returns_error_for_invalid_category() -> None:
    """Test that get_events returns an error if an unsupported category is passed from params."""
    tool = _load_tool()

    TEST_PARAMS["category"] = "fakecategory"

    with pytest.raises(ToolError) as e:
        tool.get_events(**TEST_PARAMS)

    assert "get_events ValidationError" in str(e)

    _reset_test_params()


def test_get_events_returns_error_for_invalid_status() -> None:
    """Test that get_events rejects a status value outside open/closed/all."""
    tool = _load_tool()

    TEST_PARAMS["status"] = "bogus"

    with pytest.raises(ToolError) as e:
        tool.get_events(**TEST_PARAMS)

    assert "get_events ValidationError" in str(e)

    _reset_test_params()


def test_get_events_returns_error_for_out_of_range_limit() -> None:
    """Test that get_events rejects a limit outside the 1-50 range."""
    tool = _load_tool()

    TEST_PARAMS["limit"] = 0

    with pytest.raises(ToolError) as e:
        tool.get_events(**TEST_PARAMS)

    assert "get_events ValidationError" in str(e)

    _reset_test_params()

    TEST_PARAMS["limit"] = 51

    with pytest.raises(ToolError) as e:
        tool.get_events(**TEST_PARAMS)

    assert "get_events ValidationError" in str(e)

    _reset_test_params()


def test_get_events_defaults_status_to_all(mock_events_endpoint: MagicMock) -> None:
    """Test that get_events forwards status='all' to the EONET client by default."""
    tool = _load_tool()

    mock_events_endpoint.return_value = {
        "type": "FeatureCollection",
        "features": [],
    }

    tool.get_events()

    sent_params, _ = mock_events_endpoint.call_args.args
    assert sent_params["status"] == "all"


def test_get_events_generic_error_handling(mock_events_endpoint: MagicMock) -> None:
    """Test that get_events can handle unexpected errors."""
    tool = _load_tool()

    mock_events_endpoint.return_value = []

    TEST_PARAMS["limit"] = 1

    mock_events_endpoint.side_effect = EONETError(
        f"Non-JSON response for event request with params '{list(TEST_PARAMS)}'"
    )

    with pytest.raises(ToolError) as e:
        tool.get_events(**TEST_PARAMS)

    assert f"Non-JSON response for event request with params '{list(TEST_PARAMS)}'" in str(e)

    _reset_test_params()
