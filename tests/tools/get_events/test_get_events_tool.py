"""Tests for the get_events MCP tool."""

import importlib
import types
from fastmcp.exceptions import ToolError
from collections.abc import Generator
from unittest.mock import ANY, MagicMock, patch

import pytest

from models.tools.cmr_search import SearchStatus
from util.eonet.client import (
    EONET_BASE_URL, 
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


def test_get_events_returns_event(mock_events_endpoint: MagicMock) -> None:
    """Test that get_events returns an event successfully."""
    tool = _load_tool()

    mock_events_endpoint.return_value = {
        "title": "EONET Event",
        "description": "Natural event from EONET.",
        "link": f"{EONET_BASE_URL}/events",
        "events": [{
            "id": "exampleEvent",
            "title": "Event Title",
            "description": "Event description",
            "link": f"{EONET_BASE_URL}/events/exampleEvent",
            "closed": None,
            "categories": [],
            "sources": [],
            "geometry": [],
        }],
    }

    expected = {
        "status": SearchStatus.SUCCESS,
        "error_message": None,
        "title": "EONET Event",
        "description": "Natural event from EONET.",
        "link": f"{EONET_BASE_URL}/events",
        "type": "",
        "data": [{
            "id": "exampleEvent",
            "title": "Event Title",
            "description": "Event description",
            "link": f"{EONET_BASE_URL}/events/exampleEvent",
            "closed": None,
            "categories": [],
            "sources": [],
            "geometry": [],
        }],
    }

    params = {"limit": "1"}

    result = tool.get_events(endpoint="events", params=params)

    assert result["status"] == expected["status"]
    assert result["error_message"] == expected["error_message"]
    assert result["title"] == expected["title"]
    assert result["description"] == expected["description"]
    assert result["link"] == expected["link"]
    assert result["type"] == expected["type"]
    assert result["data"] == expected["data"]
    mock_events_endpoint.assert_called_once_with(params, False)


def test_get_events_returns_multiple_events(mock_events_endpoint: MagicMock) -> None:
    """Test that get_events returns multiple results successfully."""
    tool = _load_tool()
    
    mock_events_endpoint.return_value = {
        "title": "EONET Event",
        "description": "Natural events from EONET.",
        "link": f"{EONET_BASE_URL}/events",
        "events": [{
            "id": "exampleEvent",
            "title": "Event Title",
            "description": "Event description",
            "link": f"{EONET_BASE_URL}/events/exampleEvent",
            "closed": None,
            "categories": [],
            "sources": [],
            "geometry": [],
        },
        {
            "id": "exampleEvent2",
            "title": "Event2 Title",
            "description": "Event2 description",
            "link": f"{EONET_BASE_URL}/events/exampleEvent2",
            "closed": None,
            "categories": [],
            "sources": [],
            "geometry": [],
        }],
    }

    expected = {
        "status": SearchStatus.SUCCESS,
        "error_message": None,
        "title": "EONET Event",
        "description": "Natural events from EONET.",
        "link": f"{EONET_BASE_URL}/events",
        "type": "",
        "data": [{
            "id": "exampleEvent",
            "title": "Event Title",
            "description": "Event description",
            "link": f"{EONET_BASE_URL}/events/exampleEvent",
            "closed": None,
            "categories": [],
            "sources": [],
            "geometry": [],
        },
        {
            "id": "exampleEvent2",
            "title": "Event2 Title",
            "description": "Event2 description",
            "link": f"{EONET_BASE_URL}/events/exampleEvent2",
            "closed": None,
            "categories": [],
            "sources": [],
            "geometry": [],
        }],
    }

    params = {"limit": "2"}
    
    result = tool.get_events(endpoint="events", params=params)

    assert result["status"] == expected["status"]
    assert result["error_message"] == expected["error_message"]
    assert result["title"] == expected["title"]
    assert result["description"] == expected["description"]
    assert result["link"] == expected["link"]
    assert result["type"] == expected["type"]
    assert result["data"] == expected["data"]
    mock_events_endpoint.assert_called_once_with(params, False)


def test_get_events_returns_no_events(mock_events_endpoint: MagicMock) -> None:
    """Test that get_events can return no results successfully."""
    tool = _load_tool()
        
    mock_events_endpoint.return_value = {
        "title": "EONET Events",
        "description": "Natural events from EONET.",
        "link": f"{EONET_BASE_URL}/events",
        "events": [],
    }

    expected = {
        "status": SearchStatus.NO_RESULTS,
        "error_message": None,
        "title": "EONET Events",
        "description": "Natural events from EONET.",
        "link": f"{EONET_BASE_URL}/events",
        "type": "",
        "data": [],
    }

    params = {"limit": "1"}
        
    result = tool.get_events(endpoint="events", params=params)

    assert result["status"] == expected["status"]
    assert result["error_message"] == expected["error_message"]
    assert result["title"] == expected["title"]
    assert result["description"] == expected["description"]
    assert result["link"] == expected["link"]
    assert result["type"] == expected["type"]
    assert result["data"] == expected["data"]
    mock_events_endpoint.assert_called_once_with(params, False)


def test_get_events_returns_all_events_on_failed_api_call(mock_events_endpoint: MagicMock) -> None:
    """Test that get_events returns all results if an invalid EONET request is made."""
    tool = _load_tool()
            
    mock_events_endpoint.return_value = {
        "title": "EONET Event",
        "description": "Natural events from EONET.",
        "link": f"{EONET_BASE_URL}/events",
        "events": [{
            "id": "exampleEvent",
            "title": "Event Title",
            "description": "Event description",
            "link": f"{EONET_BASE_URL}/events/exampleEvent",
            "closed": None,
            "categories": [],
            "sources": [],
            "geometry": [],
        },
        {
            "id": "exampleEvent2",
            "title": "Event2 Title",
            "description": "Event2 description",
            "link": f"{EONET_BASE_URL}/events/exampleEvent2",
            "closed": None,
            "categories": [],
            "sources": [],
            "geometry": [],
        }],
    }

    expected = {
        "status": SearchStatus.SUCCESS,
        "error_message": None,
        "title": "EONET Event",
        "description": "Natural events from EONET.",
        "link": f"{EONET_BASE_URL}/events",
        "type": "",
        "data": [{
            "id": "exampleEvent",
            "title": "Event Title",
            "description": "Event description",
            "link": f"{EONET_BASE_URL}/events/exampleEvent",
            "closed": None,
            "categories": [],
            "sources": [],
            "geometry": [],
        },
        {
            "id": "exampleEvent2",
            "title": "Event2 Title",
            "description": "Event2 description",
            "link": f"{EONET_BASE_URL}/events/exampleEvent2",
            "closed": None,
            "categories": [],
            "sources": [],
            "geometry": [],
        }],
    }
    
    params = {"limit": "-1"}
            
    result = tool.get_events(endpoint="events", params=params)

    assert result["status"] == expected["status"]
    assert result["error_message"] == expected["error_message"]
    assert result["title"] == expected["title"]
    assert result["description"] == expected["description"]
    assert result["link"] == expected["link"]
    assert result["type"] == expected["type"]
    assert result["data"] == expected["data"]
    mock_events_endpoint.assert_called_once_with(params, False)


def test_get_events_returns_event_geojson(mock_events_endpoint: MagicMock) -> None:
    """Test that get_events can return a geojson result successfully."""
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
        "title": "",
        "description": "",
        "link": "",
        "type": "FeatureCollection",
        "data": [{
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

    params = {"limit": "1"}

    result = tool.get_events(endpoint="events/geojson", params=params)

    assert result["status"] == expected["status"]
    assert result["error_message"] == expected["error_message"]
    assert result["title"] == expected["title"]
    assert result["description"] == expected["description"]
    assert result["link"] == expected["link"]
    assert result["type"] == expected["type"]
    assert result["data"] == expected["data"]
    mock_events_endpoint.assert_called_once_with(params, True)


def test_get_events_returns_multiple_events_geojson(mock_events_endpoint: MagicMock) -> None:
    """Test that get_events can return multiple geojson results successfully."""
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
        "title": "",
        "description": "",
        "link": "",
        "type": "FeatureCollection",
        "data": [{
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

    params = {"limit": "2"}

    result = tool.get_events(endpoint="events/geojson", params=params)

    assert result["status"] == expected["status"]
    assert result["error_message"] == expected["error_message"]
    assert result["title"] == expected["title"]
    assert result["description"] == expected["description"]
    assert result["link"] == expected["link"]
    assert result["type"] == expected["type"]
    assert result["data"] == expected["data"]
    mock_events_endpoint.assert_called_once_with(params, True)


def test_get_events_returns_no_events_geojson(mock_events_endpoint: MagicMock) -> None:
    """Test that get_events can return no geojson results successfully."""
    tool = _load_tool()
                        
    mock_events_endpoint.return_value = {
        "type": "FeatureCollection",
        "features": [],
    }

    expected = {
        "status": SearchStatus.NO_RESULTS,
        "error_message": None,
        "title": "",
        "description": "",
        "link": "",
        "type": "FeatureCollection",
        "data": [],
    }

    params = {"limit": "1"}

    result = tool.get_events(endpoint="events/geojson", params=params)

    assert result["status"] == expected["status"]
    assert result["error_message"] == expected["error_message"]
    assert result["title"] == expected["title"]
    assert result["description"] == expected["description"]
    assert result["link"] == expected["link"]
    assert result["type"] == expected["type"]
    assert result["data"] == expected["data"]
    mock_events_endpoint.assert_called_once_with(params, True)


def test_get_events_returns_all_geojson_results_on_failed_api_call(mock_events_endpoint: MagicMock) -> None:
    """Test that get_events returns all results if an invalid geojson request is made."""
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
        "title": "",
        "description": "",
        "link": "",
        "type": "FeatureCollection",
        "data": [{
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
    
    params = {"limit": "-1"}
    
    result = tool.get_events(endpoint="events/geojson", params=params)

    assert result["status"] == expected["status"]
    assert result["error_message"] == expected["error_message"]
    assert result["title"] == expected["title"]
    assert result["description"] == expected["description"]
    assert result["link"] == expected["link"]
    assert result["type"] == expected["type"]
    assert result["data"] == expected["data"]
    mock_events_endpoint.assert_called_once_with(params, True)


def test_get_events_returns_error_for_bad_eonet_connection(mock_events_endpoint: MagicMock) -> None:
    """Test that get_events returns an error if it can't reach the EONET API."""
    tool = _load_tool()

    mock_events_endpoint.side_effect=EONETError(f"Failed to fetch events from EONET: {ANY}")

    params = {"limit": "1"}

    results = tool.get_events(endpoint="events", params=params)

    assert "Failed to fetch events from EONET" in results["error_message"]


def test_get_events_returns_error_for_invalid_endpoint() -> None:
    """Test that get_events returns an error if an invalid endpoint is given."""
    tool = _load_tool()

    results = tool.get_events(endpoint="invalid_endpoint", params={})

    assert results["error_message"] == "Provided endpoint does not exist or is not supported: 'invalid_endpoint'"


def test_get_events_returns_error_for_malformed_event_json(mock_events_endpoint: MagicMock) -> None:
    """Test that get_events returns an error if event results are malformed."""
    tool = _load_tool()
                
    mock_events_endpoint.return_value = {
        "title": "EONET Events",
        "description": "Natural events from EONET.",
        "link": f"{EONET_BASE_URL}/events",
    }

    mock_events_endpoint.side_effect=EONETError(
        "Unexpected response shape for events request. Response did not contain 'events' key."
    )

    params = {"limit": "1"}

    result = tool.get_events(endpoint="events", params=params)

    assert "Unexpected response shape for events request. Response did not contain 'events' key." \
        in result["error_message"]


def test_get_events_returns_error_for_malformed_geojson(mock_events_endpoint: MagicMock) -> None:
    """Test that get_events returns an error if GeoJSON results are malformed."""
    tool = _load_tool()
                
    mock_events_endpoint.return_value = {}

    mock_events_endpoint.side_effect=EONETError(
        "Unexpected response shape for geojson request. Response did not contain 'features' and/or 'type' key."
    )

    params = {"limit": "1"}

    result = tool.get_events(endpoint="events/geojson", params=params)

    assert "Unexpected response shape for geojson request. Response did not contain 'features' and/or 'type' key." \
        in result["error_message"]


def test_get_events_returns_all_events_for_fake_category(mock_events_endpoint: MagicMock) -> None:
    """Test that get_events returns all events if a fake category is given."""
    tool = _load_tool()
                                
    mock_events_endpoint.return_value = {
        "title": "EONET Event",
        "description": "Natural events from EONET.",
        "link": f"{EONET_BASE_URL}/events",
        "events": [{
            "id": "exampleEvent",
            "title": "Event Title",
            "description": "Event description",
            "link": f"{EONET_BASE_URL}/events/exampleEvent",
            "closed": None,
            "categories": [],
            "sources": [],
            "geometry": [],
        },
        {
            "id": "exampleEvent2",
            "title": "Event2 Title",
            "description": "Event2 description",
            "link": f"{EONET_BASE_URL}/events/exampleEvent2",
            "closed": None,
            "categories": [],
            "sources": [],
            "geometry": [],
        }],
    }

    expected = {
        "status": SearchStatus.SUCCESS,
        "error_message": None,
        "title": "EONET Event",
        "description": "Natural events from EONET.",
        "link": f"{EONET_BASE_URL}/events",
        "type": "",
        "data": [{
            "id": "exampleEvent",
            "title": "Event Title",
            "description": "Event description",
            "link": f"{EONET_BASE_URL}/events/exampleEvent",
            "closed": None,
            "categories": [],
            "sources": [],
            "geometry": [],
        },
        {
            "id": "exampleEvent2",
            "title": "Event2 Title",
            "description": "Event2 description",
            "link": f"{EONET_BASE_URL}/events/exampleEvent2",
            "closed": None,
            "categories": [],
            "sources": [],
            "geometry": [],
        }],
    }

    params = {"category": "fakecategory"}

    result = tool.get_events(endpoint="events", params=params)

    expected_params = {"category": "fakecategory", "limit": 5}

    assert result["status"] == expected["status"]
    assert result["error_message"] == expected["error_message"]
    assert result["title"] == expected["title"]
    assert result["description"] == expected["description"]
    assert result["link"] == expected["link"]
    assert result["type"] == expected["type"]
    assert result["data"] == expected["data"]
    mock_events_endpoint.assert_called_once_with(expected_params, False)


def test_get_events_sets_omitted_optional_event_fields(mock_events_endpoint: MagicMock) -> None:
    """Test that get_events will automatically fill in missing event fields from EONET response."""
    tool = _load_tool()
    
    mock_events_endpoint.return_value = {
            "title": "EONET Event",
            "description": "Natural event from EONET.",
            "link": f"{EONET_BASE_URL}/events",
            "events": [{
                "id": "exampleEvent",
            }],
        }
    
    expected = {
        "status": SearchStatus.SUCCESS,
        "error_message": None,
        "title": "EONET Event",
        "description": "Natural event from EONET.",
        "link": f"{EONET_BASE_URL}/events",
        "type": "",
        "data": [{
            "id": "exampleEvent",
            "title": "",
            "description": "",
            "link": f"{EONET_BASE_URL}/events/exampleEvent",
            "closed": None,
            "categories": [],
            "sources": [],
            "geometry": [],
        }],
    }
    
    params = {"limit": "1"}
    
    result = tool.get_events(endpoint="events", params=params)
    
    assert "description" in result["data"][0] and result["data"][0]["description"] == expected["data"][0]["description"]
