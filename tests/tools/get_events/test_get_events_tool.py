"""Tests for the get_events MCP tool."""

import importlib
import types
from fastmcp.exceptions import ToolError
from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

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
    "status": None,
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
        "features": [{
            "type": "Feature",
            "geometry": {
              "type": "Point",
              "coordinates": [0.0, 0.0] 
            },
            "properties": {
              "name": "A Cool Place",
              "location": "Anytown, USA"
            }
        }],
    }

    expected = {
        "status": SearchStatus.SUCCESS,
        "error_message": None,
        "data": {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "geometry": {
                  "type": "Point",
                  "coordinates": [0.0, 0.0] 
                },
                "properties": {
                  "name": "A Cool Place",
                  "location": "Anytown, USA"
                }
            }],
        },
    }

    TEST_PARAMS["limit"] = 1

    result = tool.get_events(**TEST_PARAMS)

    assert result["status"] == expected["status"]
    assert result["error_message"] == expected["error_message"]
    assert result["data"] == expected["data"]
    mock_events_endpoint.assert_called_once_with(TEST_PARAMS, True)


def test_get_events_returns_multiple_events(mock_events_endpoint: MagicMock) -> None:
    """Test that get_events can return multiple results successfully."""
    tool = _load_tool()
                    
    mock_events_endpoint.return_value = {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "geometry": {
              "type": "Point",
              "coordinates": [0.0, 0.0] 
            },
            "properties": {
              "name": "A Cool Place",
              "location": "Anytown, USA"
            }
        },
        {
            "type": "Feature",
            "geometry": {
              "type": "Point",
              "coordinates": [1.0, 1.0] 
            },
            "properties": {
              "name": "Another Cool Place",
              "location": "Anothertown, USA"
            }
        }],
    }

    expected = {
        "status": SearchStatus.SUCCESS,
        "error_message": None,
        "data": {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "geometry": {
                  "type": "Point",
                  "coordinates": [0.0, 0.0] 
                },
                "properties": {
                  "name": "A Cool Place",
                  "location": "Anytown, USA"
                }
            },
            {
                "type": "Feature",
                "geometry": {
                  "type": "Point",
                  "coordinates": [1.0, 1.0] 
                },
                "properties": {
                  "name": "Another Cool Place",
                  "location": "Anothertown, USA"
                }
            }],
        },
    }

    TEST_PARAMS["limit"] = 2

    result = tool.get_events(**TEST_PARAMS)

    assert result["status"] == expected["status"]
    assert result["error_message"] == expected["error_message"]
    assert result["data"] == expected["data"]
    mock_events_endpoint.assert_called_once_with(TEST_PARAMS, True)


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


def test_get_events_filters_by_category(mock_events_endpoint: MagicMock) -> None:
    """Test that get_events can filter results (i.e. by category)."""
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


def test_get_events_returns_all_events_on_failed_api_call(mock_events_endpoint: MagicMock) -> None:
    """Test that get_events returns all results if an invalid request is made."""
    tool = _load_tool()
                            
    mock_events_endpoint.return_value = {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "geometry": {
              "type": "Point",
              "coordinates": [0.0, 0.0] 
            },
            "properties": {
              "name": "A Cool Place",
              "location": "Anytown, USA"
            }
        },
        {
            "type": "Feature",
            "geometry": {
              "type": "Point",
              "coordinates": [1.0, 1.0] 
            },
            "properties": {
              "name": "Another Cool Place",
              "location": "Anothertown, USA"
            }
        }],
    }

    expected = {
        "status": SearchStatus.SUCCESS,
        "error_message": None,
        "data": {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "geometry": {
                  "type": "Point",
                  "coordinates": [0.0, 0.0] 
                },
                "properties": {
                  "name": "A Cool Place",
                  "location": "Anytown, USA"
                }
            },
            {
                "type": "Feature",
                "geometry": {
                  "type": "Point",
                  "coordinates": [1.0, 1.0] 
                },
                "properties": {
                  "name": "Another Cool Place",
                  "location": "Anothertown, USA"
                }
            }],
        },
    }
    
    TEST_PARAMS["limit"] = -1
    
    result = tool.get_events(**TEST_PARAMS)

    assert result["status"] == expected["status"]
    assert result["error_message"] == expected["error_message"]
    assert result["data"] == expected["data"]
    mock_events_endpoint.assert_called_once_with(TEST_PARAMS, True)


def test_get_events_returns_error_for_invalid_input() -> None:
    """Test that get_events returns an error if invalid input is passed to params."""
    tool = _load_tool()
    
    TEST_PARAMS["source"] = 123
    
    with pytest.raises(ToolError) as e:
        tool.get_events(**TEST_PARAMS)
    
    assert f"get_events ValidationError" in str(e)


def test_get_events_returns_error_for_bad_eonet_connection(mock_events_endpoint: MagicMock) -> None:
    """Test that get_events returns an error if it can't reach the EONET API."""
    tool = _load_tool()

    mock_events_endpoint.side_effect=EONETError(f"Failed to fetch events from EONET")

    TEST_PARAMS["limit"] = 1

    with pytest.raises(ToolError) as e:
        tool.get_events(**TEST_PARAMS)

    assert "Failed to fetch events from EONET" in str(e)


def test_get_events_returns_error_for_malformed_event_results(mock_events_endpoint: MagicMock) -> None:
    """Test that get_events returns an error if results are malformed."""
    tool = _load_tool()
                
    mock_events_endpoint.return_value = {}

    mock_events_endpoint.side_effect=EONETError("Unexpected response shape: 'features' and/or 'type' keys missing.")

    TEST_PARAMS["limit"] = 1

    with pytest.raises(ToolError) as e:
        tool.get_events(**TEST_PARAMS)

    assert "Unexpected response shape: 'features' and/or 'type' keys missing." in str(e)


def test_get_events_returns_error_for_fake_category() -> None:
    """Test that get_events returns an error if a fake category is passed from params."""
    tool = _load_tool()
    
    TEST_PARAMS["category"] = "fakecategory"
    
    with pytest.raises(ToolError) as e:
        tool.get_events(**TEST_PARAMS)
    
    assert f"get_events ValidationError" in str(e)


def test_get_events_generic_error_handling(mock_events_endpoint: MagicMock) -> None:
    """Test that get_events can handle unexpected errors."""
    tool = _load_tool()

    mock_events_endpoint.return_value = []

    mock_events_endpoint.side_effect=EONETError("Non-JSON response for event request")
    
    TEST_PARAMS["limit"] = 1
    
    with pytest.raises(ToolError) as e:
        tool.get_events(**TEST_PARAMS)
    
    assert f"Non-JSON response for event request with params '{list(TEST_PARAMS)}'" in str(e)
