"""Tests for the get_events MCP tool."""

import importlib
import types
from fastmcp.exceptions import ToolError
from collections.abc import Generator
from unittest.mock import MagicMock, patch, ANY

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

@pytest.fixture
def mock_categories_endpoint() -> Generator[MagicMock]:
    """Mock tools.get_events.tool.categories."""
    with patch("tools.get_events.tool.categories") as mock_categories:
        yield mock_categories

@pytest.fixture
def mock_layers_endpoint() -> Generator[MagicMock]:
    """Mock tools.get_events.tool.layers."""
    with patch("tools.get_events.tool.layers") as mock_layers:
        yield mock_layers


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
        "title": "EONET Event",
        "description": "Natural event from EONET.",
        "link": f"{EONET_BASE_URL}/events",
        "type": "",
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
        "features": [],
        "categories": [],
    }

    params = {"limit": "1"}

    result = tool.get_events(endpoint="events", params=params, event_id="", category="")

    assert result["status"] == expected["status"]
    assert result["title"] == expected["title"]
    assert result["description"] == expected["description"]
    assert result["link"] == expected["link"]
    assert result["type"] == expected["type"]
    assert result["events"] == expected["events"]
    assert result["features"] == expected["features"]
    assert result["categories"] == expected["categories"]
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
        "title": "EONET Event",
        "description": "Natural events from EONET.",
        "link": f"{EONET_BASE_URL}/events",
        "type": "",
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
        "features": [],
        "categories": [],
    }

    params = {"limit": "2"}
    
    result = tool.get_events(endpoint="events", params=params, event_id="", category="")

    assert result["status"] == expected["status"]
    assert result["title"] == expected["title"]
    assert result["description"] == expected["description"]
    assert result["link"] == expected["link"]
    assert result["type"] == expected["type"]
    assert result["events"] == expected["events"]
    assert result["features"] == expected["features"]
    assert result["categories"] == expected["categories"]
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
        "title": "EONET Events",
        "description": "Natural events from EONET.",
        "link": f"{EONET_BASE_URL}/events",
        "type": "",
        "events": [],
        "features": [],
        "categories": [],
    }

    params = {"limit": "1"}
        
    result = tool.get_events(endpoint="events", params=params, event_id="", category="")

    assert result["status"] == expected["status"]
    assert result["title"] == expected["title"]
    assert result["description"] == expected["description"]
    assert result["link"] == expected["link"]
    assert result["type"] == expected["type"]
    assert result["events"] == expected["events"]
    assert result["features"] == expected["features"]
    assert result["categories"] == expected["categories"]
    mock_events_endpoint.assert_called_once_with(params, False)


def test_get_events_call_failed(mock_events_endpoint: MagicMock) -> None:
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
        "title": "EONET Event",
        "description": "Natural events from EONET.",
        "link": f"{EONET_BASE_URL}/events",
        "type": "",
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
        "features": [],
        "categories": [],
    }
    
    params = {"limit": "-1"}
            
    result = tool.get_events(endpoint="events", params=params, event_id="", category="")

    assert result["status"] == expected["status"]
    assert result["title"] == expected["title"]
    assert result["description"] == expected["description"]
    assert result["link"] == expected["link"]
    assert result["type"] == expected["type"]
    assert result["events"] == expected["events"]
    assert result["features"] == expected["features"]
    assert result["categories"] == expected["categories"]
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
        "title": "",
        "description": "",
        "link": "",
        "type": "FeatureCollection",
        "events": [],
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
        "categories": [],
    }

    params = {"limit": "1"}

    result = tool.get_events(endpoint="events/geojson", params=params, event_id="", category="")

    assert result["status"] == expected["status"]
    assert result["title"] == expected["title"]
    assert result["description"] == expected["description"]
    assert result["link"] == expected["link"]
    assert result["type"] == expected["type"]
    assert result["events"] == expected["events"]
    assert result["features"] == expected["features"]
    assert result["categories"] == expected["categories"]
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
        "title": "",
        "description": "",
        "link": "",
        "type": "FeatureCollection",
        "events": [],
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
        "categories": [],
    }

    params = {"limit": "2"}

    result = tool.get_events(endpoint="events/geojson", params=params, event_id="", category="")

    assert result["status"] == expected["status"]
    assert result["title"] == expected["title"]
    assert result["description"] == expected["description"]
    assert result["link"] == expected["link"]
    assert result["type"] == expected["type"]
    assert result["events"] == expected["events"]
    assert result["features"] == expected["features"]
    assert result["categories"] == expected["categories"]
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
        "title": "",
        "description": "",
        "link": "",
        "type": "FeatureCollection",
        "events": [],
        "features": [],
        "categories": [], 
    }

    params = {"limit": "1"}

    result = tool.get_events(endpoint="events/geojson", params=params, event_id="", category="")

    assert result["status"] == expected["status"]
    assert result["title"] == expected["title"]
    assert result["description"] == expected["description"]
    assert result["link"] == expected["link"]
    assert result["type"] == expected["type"]
    assert result["events"] == expected["events"]
    assert result["features"] == expected["features"]
    assert result["categories"] == expected["categories"]
    mock_events_endpoint.assert_called_once_with(params, True)


def test_get_events_geojson_return_failed(mock_events_endpoint: MagicMock) -> None:
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
        "title": "",
        "description": "",
        "link": "",
        "type": "FeatureCollection",
        "events": [],
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
        "categories": [],
    }
    
    params = {"limit": "-1"}
    
    result = tool.get_events(endpoint="events/geojson", params=params, event_id="", category="")

    assert result["status"] == expected["status"]
    assert result["title"] == expected["title"]
    assert result["description"] == expected["description"]
    assert result["link"] == expected["link"]
    assert result["type"] == expected["type"]
    assert result["events"] == expected["events"]
    assert result["features"] == expected["features"]
    assert result["categories"] == expected["categories"]
    mock_events_endpoint.assert_called_once_with(params, True)


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
        "title": "EONET Event",
        "description": "Natural events from EONET.",
        "link": f"{EONET_BASE_URL}/events",
        "type": "",
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
        "features": [],
        "categories": [],
    }

    params = {"category": "fakecategory"}

    result = tool.get_events(endpoint="events", params=params, event_id="", category="")

    expected_params = {"category": "fakecategory", "limit": 5}

    assert result["status"] == expected["status"]
    assert result["title"] == expected["title"]
    assert result["description"] == expected["description"]
    assert result["link"] == expected["link"]
    assert result["type"] == expected["type"]
    assert result["events"] == expected["events"]
    assert result["features"] == expected["features"]
    assert result["categories"] == expected["categories"]
    mock_events_endpoint.assert_called_once_with(expected_params, False)


def test_get_events_returns_event_from_category(mock_categories_endpoint: MagicMock) -> None:
    """Test that get_events returns events from the specified category."""
    tool = _load_tool()
                                    
    mock_categories_endpoint.return_value = {
        "title": "EONET Events: Category",
        "description": "Category description.",
        "link": f"{EONET_BASE_URL}/categories/categoryId",
        "events": [{
            "id": "exampleEvent",
            "title": "Event Title",
            "description": "Event description",
            "link": f"{EONET_BASE_URL}/events/exampleEvent",
            "closed": None,
            "categories": [{
                "id": "categoryId",
                "title": "Category Title",
            }],
            "sources": [],
            "geometry": [],
        }],
    }

    expected = {
        "status": SearchStatus.SUCCESS,
        "title": "EONET Events: Category",
        "description": "Category description.",
        "link": f"{EONET_BASE_URL}/categories/categoryId",
        "type": "",
        "events": [{
            "id": "exampleEvent",
            "title": "Event Title",
            "description": "Event description",
            "link": f"{EONET_BASE_URL}/events/exampleEvent",
            "closed": None,
            "categories": [{
                "id": "categoryId",
                "title": "Category Title",
                "link": "",
                "description": "",
                "layers": [],
            }],
            "sources": [],
            "geometry": [],
        }],
        "features": [],
        "categories": [],
    }

    params = {"limit": "1"}

    result = tool.get_events(endpoint="categories", params=params, event_id="", category="categoryId")

    assert result["status"] == expected["status"]
    assert result["title"] == expected["title"]
    assert result["description"] == expected["description"]
    assert result["link"] == expected["link"]
    assert result["type"] == expected["type"]
    assert result["events"] == expected["events"]
    assert result["features"] == expected["features"]
    assert result["categories"] == expected["categories"]
    mock_categories_endpoint.assert_called_once_with("categoryId", params)


def test_get_events_returns_multiple_events_from_category(mock_categories_endpoint: MagicMock) -> None:
    """Test that get_events returns multiple events from the specified category."""
    tool = _load_tool()
                                        
    mock_categories_endpoint.return_value = {
        "title": "EONET Events: Category",
        "description": "Category description.",
        "link": f"{EONET_BASE_URL}/categories/categoryId",
        "events": [{
            "id": "exampleEvent",
            "title": "Event Title",
            "description": "Event description",
            "link": f"{EONET_BASE_URL}/events/exampleEvent",
            "closed": None,
            "categories": [{
                "id": "categoryId",
                "title": "Category Title",
            }],
            "sources": [],
            "geometry": [],
        },
        {
            "id": "exampleEvent2",
            "title": "Event2 Title",
            "description": "Event2 description",
            "link": f"{EONET_BASE_URL}/events/exampleEvent2",
            "closed": None,
            "categories": [{
                "id": "categoryId",
                "title": "Category Title",
            }],
            "sources": [],
            "geometry": [],
        }],
    }

    expected = {
        "status": SearchStatus.SUCCESS,
        "title": "EONET Events: Category",
        "description": "Category description.",
        "link": f"{EONET_BASE_URL}/categories/categoryId",
        "type": "",
        "events": [{
            "id": "exampleEvent",
            "title": "Event Title",
            "description": "Event description",
            "link": f"{EONET_BASE_URL}/events/exampleEvent",
            "closed": None,
            "categories": [{
                "id": "categoryId",
                "title": "Category Title",
                "link": "",
                "description": "",
                "layers": [],
            }],
            "sources": [],
            "geometry": [],
        },
        {
            "id": "exampleEvent2",
            "title": "Event2 Title",
            "description": "Event2 description",
            "link": f"{EONET_BASE_URL}/events/exampleEvent2",
            "closed": None,
            "categories": [{
                "id": "categoryId",
                "title": "Category Title",
                "link": "",
                "description": "",
                "layers": [],
            }],
            "sources": [],
            "geometry": [],
        }],
        "features": [],
        "categories": [],
    }

    params = {"limit": "2"}

    result = tool.get_events(endpoint="categories", params=params, event_id="", category="categoryId")

    assert result["status"] == expected["status"]
    assert result["title"] == expected["title"]
    assert result["description"] == expected["description"]
    assert result["link"] == expected["link"]
    assert result["type"] == expected["type"]
    assert result["events"] == expected["events"]
    assert result["features"] == expected["features"]
    assert result["categories"] == expected["categories"]
    mock_categories_endpoint.assert_called_once_with("categoryId", params)


def test_get_events_returns_no_events_from_category(mock_categories_endpoint: MagicMock) -> None:
    """Test that get_events returns no events for a category without events."""
    tool = _load_tool()
                                            
    mock_categories_endpoint.return_value = {
        "title": "Category Title",
        "description": "Category description",
        "link": f"{EONET_BASE_URL}/categories/categoryId",
        "events": [],
    }

    expected = {
        "status": SearchStatus.NO_RESULTS,
        "title": "Category Title",
        "description": "Category description",
        "link": f"{EONET_BASE_URL}/categories/categoryId",
        "type": "",
        "events": [],
        "features": [],
        "categories": [],
    }

    params = {"limit": "1"}

    result = tool.get_events(endpoint="categories", params=params, event_id="", category="categoryId")

    assert result["status"] == expected["status"]
    assert result["title"] == expected["title"]
    assert result["description"] == expected["description"]
    assert result["link"] == expected["link"]
    assert result["type"] == expected["type"]
    assert result["events"] == expected["events"]
    assert result["features"] == expected["features"]
    assert result["categories"] == expected["categories"]
    mock_categories_endpoint.assert_called_once_with("categoryId", params)


def test_get_events_returns_all_categories(mock_categories_endpoint: MagicMock) -> None:
    """
    Test that get_events returns all categories if just the category 
    endpoint itself is passed via the request.
    """
    tool = _load_tool()
                                                
    mock_categories_endpoint.return_value = {
        "title": "EONET Event Categories",
        "description": "List of all the available event categories in the EONET system",
        "link": f"{EONET_BASE_URL}/categories",
        "categories": [{
            "id": "categoryId",
            "title": "Category Title",
            "link": f"{EONET_BASE_URL}/categories/categoryId",
            "description": "Category description.",
            "layers": f"{EONET_BASE_URL}/layers/categoryId_layers"
        },
        {
            "id": "categoryId2",
            "title": "Category2 Title",
            "link": f"{EONET_BASE_URL}/categories/categoryId2",
            "description": "Category2 description.",
            "layers": f"{EONET_BASE_URL}/layers/categoryId2_layers"
        }]
    }

    expected = {
        "status": SearchStatus.SUCCESS,
        "title": "EONET Event Categories",
        "description": "List of all the available event categories in the EONET system",
        "link": f"{EONET_BASE_URL}/categories",
        "type": "",
        "events": [],
        "features": [],
        "categories": [{
            "id": "categoryId",
            "title": "Category Title",
            "link": f"{EONET_BASE_URL}/categories/categoryId",
            "description": "Category description.",
            "layers": f"{EONET_BASE_URL}/layers/categoryId_layers"
        },
        {
            "id": "categoryId2",
            "title": "Category2 Title",
            "link": f"{EONET_BASE_URL}/categories/categoryId2",
            "description": "Category2 description.",
            "layers": f"{EONET_BASE_URL}/layers/categoryId2_layers"
        }]
    }
    
    result = tool.get_events(endpoint="categories", params={}, event_id="", category="")

    assert result["status"] == expected["status"]
    assert result["title"] == expected["title"]
    assert result["description"] == expected["description"]
    assert result["link"] == expected["link"]
    assert result["type"] == expected["type"]
    assert result["events"] == expected["events"]
    assert result["features"] == expected["features"]
    assert result["categories"] == expected["categories"]
    mock_categories_endpoint.assert_called_once_with("", {"limit": 5})


def test_get_events_returns_all_events_for_category_endpoint(mock_categories_endpoint: MagicMock) -> None   :
    """
    Test that get_events returns all events for a given category if just the category's
    endpoint is called without any parameters.
    """
    tool = _load_tool()
                                                    
    mock_categories_endpoint.return_value = {
        "title": "EONET Events: Category Title",
        "description": "Category description.",
        "link": f"{EONET_BASE_URL}/categories/categoryId",
        "events": [{
            "id": "exampleEvent",
            "title": "Event Title",
            "description": "Event description",
            "link": f"{EONET_BASE_URL}/events/exampleEvent",
            "closed": None,
            "categories": [{
                "id": "categoryId",
                "title": "Category Title",
            }],
            "sources": [],
            "geometry": [],
        },
        {
            "id": "exampleEvent2",
            "title": "Event2 Title",
            "description": "Event2 description",
            "link": f"{EONET_BASE_URL}/events/exampleEvent2",
            "closed": None,
            "categories": [{
                "id": "categoryId",
                "title": "Category Title",
            }],
            "sources": [],
            "geometry": [],
        }],
    }

    expected = {
        "status": SearchStatus.SUCCESS,
        "title": "EONET Events: Category Title",
        "description": "Category description.",
        "link": f"{EONET_BASE_URL}/categories/categoryId",
        "type": "",
        "events": [{
            "id": "exampleEvent",
            "title": "Event Title",
            "description": "Event description",
            "link": f"{EONET_BASE_URL}/events/exampleEvent",
            "closed": None,
            "categories": [{
                "id": "categoryId",
                "title": "Category Title",
                "link": "",
                "description": "",
                "layers": [],
            }],
            "sources": [],
            "geometry": [],
        },
        {
            "id": "exampleEvent2",
            "title": "Event2 Title",
            "description": "Event2 description",
            "link": f"{EONET_BASE_URL}/events/exampleEvent2",
            "closed": None,
            "categories": [{
                "id": "categoryId",
                "title": "Category Title",
                "link": "",
                "description": "",
                "layers": [],
            }],
            "sources": [],
            "geometry": [],
        }
        ],
        "features": [],
        "categories": [],
    }
    
    result = tool.get_events(endpoint="categories", params={}, event_id="", category="categoryId")

    assert result["status"] == expected["status"]
    assert result["title"] == expected["title"]
    assert result["description"] == expected["description"]
    assert result["link"] == expected["link"]
    assert result["type"] == expected["type"]
    assert result["events"] == expected["events"]
    assert result["features"] == expected["features"]
    assert result["categories"] == expected["categories"]
    mock_categories_endpoint.assert_called_once_with("categoryId", {"limit": 5})


def test_get_events_returns_all_events_for_category_endpoint_invalid_params(mock_categories_endpoint: MagicMock) -> None   :
    """
    Test that get_events returns all events for a given category if just the category's
    endpoint is called with an invalid parameter.
    """
    tool = _load_tool()
                                                    
    mock_categories_endpoint.return_value = {
        "title": "EONET Events: Category Title",
        "description": "Category description.",
        "link": f"{EONET_BASE_URL}/categories/categoryId",
        "events": [{
            "id": "exampleEvent",
            "title": "Event Title",
            "description": "Event description",
            "link": f"{EONET_BASE_URL}/events/exampleEvent",
            "closed": None,
            "categories": [{
                "id": "categoryId",
                "title": "Category Title",
            }],
            "sources": [],
            "geometry": [],
        },
        {
            "id": "exampleEvent2",
            "title": "Event2 Title",
            "description": "Event2 description",
            "link": f"{EONET_BASE_URL}/events/exampleEvent2",
            "closed": None,
            "categories": [{
                "id": "categoryId",
                "title": "Category Title",
            }],
            "sources": [],
            "geometry": [],
        }],
    }

    expected = {
        "status": SearchStatus.SUCCESS,
        "title": "EONET Events: Category Title",
        "description": "Category description.",
        "link": f"{EONET_BASE_URL}/categories/categoryId",
        "type": "",
        "events": [{
            "id": "exampleEvent",
            "title": "Event Title",
            "description": "Event description",
            "link": f"{EONET_BASE_URL}/events/exampleEvent",
            "closed": None,
            "categories": [{
                "id": "categoryId",
                "title": "Category Title",
                "link": "",
                "description": "",
                "layers": [],
            }],
            "sources": [],
            "geometry": [],
        },
        {
            "id": "exampleEvent2",
            "title": "Event2 Title",
            "description": "Event2 description",
            "link": f"{EONET_BASE_URL}/events/exampleEvent2",
            "closed": None,
            "categories": [{
                "id": "categoryId",
                "title": "Category Title",
                "link": "",
                "description": "",
                "layers": [],
            }],
            "sources": [],
            "geometry": [],
        }],
        "features": [],
        "categories": [],
    }

    params = { "limit": "-1" }

    result = tool.get_events(endpoint="categories", params=params, event_id="", category="categoryId")

    assert result["status"] == expected["status"]
    assert result["title"] == expected["title"]
    assert result["description"] == expected["description"]
    assert result["link"] == expected["link"]
    assert result["type"] == expected["type"]
    assert result["events"] == expected["events"]
    assert result["features"] == expected["features"]
    assert result["categories"] == expected["categories"]
    mock_categories_endpoint.assert_called_once_with("categoryId", params)


def test_get_events_categories_returns_error_for_fake_category(mock_categories_endpoint: MagicMock) -> None:
    """Test that get_events returns an error for a fake category (for category endpoint)."""
    tool = _load_tool()

    mock_categories_endpoint.side_effect=EONETError(f"Failed to fetch events for category 'fakecategory', or all categories, from EONET: {ANY}")

    with pytest.raises(ToolError) as e:
        results = tool.get_events(endpoint="categories", params={}, event_id="", category="fakecategory")
        
    assert "Failed to fetch events for category 'fakecategory'" in str(e.value)


def test_get_events_returns_layer_from_category(mock_layers_endpoint: MagicMock) -> None:
    """Test that get_events can return a single layer from the specified category."""
    tool = _load_tool()

    mock_layers_endpoint.return_value = {
        "title": "EONET Web Service Layers",
        "description": "List of web service layers in the EONET system.",
        "link": f"{EONET_BASE_URL}/layers/categoryId",
        "categories": [{
            "id": "categoryId",
            "title": "Category Title",
            "layers": [{
                "name": "layerName",
                "serviceUrl": "https://www.layer-service.com",
                "serviceTypeId": "typeId",
                "parameters": [
                    {
                        "param1": "value1",
                        "param2": "value2"
                    }
                ]
            }]
        }]
    }

    expected = {
        "status": SearchStatus.SUCCESS,
        "title": "EONET Web Service Layers",
        "description": "List of web service layers in the EONET system.",
        "link": f"{EONET_BASE_URL}/layers/categoryId",
        "type": "",
        "events": [],
        "features": [],
        "categories": [{
            "id": "categoryId",
            "title": "Category Title",
            "link": "",
            "description": "",
            "layers": [{
                "name": "layerName",
                "serviceUrl": "https://www.layer-service.com",
                "serviceTypeId": "typeId",
                "parameters": [
                    {
                        "param1": "value1",
                        "param2": "value2"
                    }
                ]
            }]
        }]
    }
    
    result = tool.get_events(endpoint="layers", params={}, event_id="", category="categoryId")

    assert result["status"] == expected["status"]
    assert result["title"] == expected["title"]
    assert result["description"] == expected["description"]
    assert result["link"] == expected["link"]
    assert result["type"] == expected["type"]
    assert result["events"] == expected["events"]
    assert result["features"] == expected["features"]
    assert result["categories"] == expected["categories"]
    mock_layers_endpoint.assert_called_once_with("categoryId")


def test_get_events_returns_multiple_layers_from_category(mock_layers_endpoint: MagicMock) -> None:
    """Test that get_events returns multiple layers from the specified category."""
    tool = _load_tool()
    
    mock_layers_endpoint.return_value = {
        "title": "EONET Web Service Layers",
        "description": "List of web service layers in the EONET system.",
        "link": f"{EONET_BASE_URL}/layers/categoryId",
        "categories": [{
            "id": "categoryId",
            "title": "Category Title",
            "layers": [{
                "name": "layerName",
                "serviceUrl": "https://www.layer-service.com",
                "serviceTypeId": "typeId",
                "parameters": [
                    {
                        "layer1param1": "layer1value1",
                        "layer1param2": "layer1value2"
                    }
                ]
            },
            {
                "name": "layer2Name",
                "serviceUrl": "https://www.layer2-service.com",
                "serviceTypeId": "typeId2",
                "parameters": [
                    {
                        "layer2Param1": "layer2Value1",
                        "layer2Param2": "layer2Value2"
                    }
                ]
            }]
        }]
    }

    expected = {
        "status": SearchStatus.SUCCESS,
        "title": "EONET Web Service Layers",
        "description": "List of web service layers in the EONET system.",
        "link": f"{EONET_BASE_URL}/layers/categoryId",
        "type": "",
        "events": [],
        "features": [],
        "categories": [{
            "id": "categoryId",
            "title": "Category Title",
            "link": "",
            "description": "",
            "layers": [{
                "name": "layerName",
                "serviceUrl": "https://www.layer-service.com",
                "serviceTypeId": "typeId",
                "parameters": [
                    {
                        "layer1param1": "layer1value1",
                        "layer1param2": "layer1value2"
                    }
                ]
            },
            {
                "name": "layer2Name",
                "serviceUrl": "https://www.layer2-service.com",
                "serviceTypeId": "typeId2",
                "parameters": [
                    {
                        "layer2Param1": "layer2Value1",
                        "layer2Param2": "layer2Value2"
                    }
                ]
            }]
        }]
    }
    
    result = tool.get_events(endpoint="layers", params={}, event_id="", category="categoryId")

    assert result["status"] == expected["status"]
    assert result["title"] == expected["title"]
    assert result["description"] == expected["description"]
    assert result["link"] == expected["link"]
    assert result["type"] == expected["type"]
    assert result["events"] == expected["events"]
    assert result["features"] == expected["features"]
    assert result["categories"] == expected["categories"]
    mock_layers_endpoint.assert_called_once_with("categoryId")


def test_get_events_returns_no_layers_from_category(mock_layers_endpoint: MagicMock) -> None:
    """Test that get_events returns no layers for a category without layers."""
    tool = _load_tool()
        
    mock_layers_endpoint.return_value = {
        "title": "EONET Web Service Layers",
        "description": "List of web service layers in the EONET system.",
        "link": f"{EONET_BASE_URL}/layers/categoryId",
        "categories": [{
            "id": "categoryId",
            "title": "Category Title",
            "layers": []
        }]
    }

    expected = {
        "status": SearchStatus.NO_RESULTS,
        "title": "EONET Web Service Layers",
        "description": "List of web service layers in the EONET system.",
        "link": f"{EONET_BASE_URL}/layers/categoryId",
        "type": "",
        "events": [],
        "features": [],
        "categories": [{
            "id": "categoryId",
            "title": "Category Title",
            "link": "",
            "description": "",
            "layers": []
        }]
    }
    
    result = tool.get_events(endpoint="layers", params={}, event_id="", category="categoryId")

    assert result["status"] == expected["status"]
    assert result["title"] == expected["title"]
    assert result["description"] == expected["description"]
    assert result["link"] == expected["link"]
    assert result["type"] == expected["type"]
    assert result["events"] == expected["events"]
    assert result["features"] == expected["features"]
    assert result["categories"] == expected["categories"]
    assert result["categories"][0]["layers"] == expected["categories"][0]["layers"]
    mock_layers_endpoint.assert_called_once_with("categoryId")


def test_get_events_returns_all_layers(mock_layers_endpoint: MagicMock) -> None:
    """Test that get_events returns all layers when no category is given."""
    tool = _load_tool()
            
    mock_layers_endpoint.return_value = {
        "title": "EONET Web Service Layers",
        "description": "List of web service layers in the EONET system",
        "link": f"{EONET_BASE_URL}/layers",
        "categories": [{
            "layers": [{
                "name": "Layer_01",
                "serviceUrl": "https://gibs.earthdata.nasa.gov/link/to/Layer_01",
                "serviceTypeId": "Layer_01_ID",
                "parameters": [
                    {
                        "TILEMATRIXSET": "2km",
                        "FORMAT": "image/png"
                    }
                ]
            },
            {
                "name": "Layer_02",
                "serviceUrl": "https://gibs.earthdata.nasa.gov/link/to/Layer_02",
                "serviceTypeId": "Layer_02_ID",
                "parameters": [
                    {
                        "TILEMATRIXSET": "2km",
                        "FORMAT": "image/png"
                    }
                ]
            }]
        }]
    }

    expected = {
        "status": SearchStatus.SUCCESS,
        "title": "EONET Web Service Layers",
        "description": "List of web service layers in the EONET system",
        "link": f"{EONET_BASE_URL}/layers",
        "type": "",
        "events": [],
        "features": [],
        "categories": [{
            "id": "",
            "title": "",
            "link": "",
            "description": "",
            "layers": [{
                "name": "Layer_01",
                "serviceUrl": "https://gibs.earthdata.nasa.gov/link/to/Layer_01",
                "serviceTypeId": "Layer_01_ID",
                "parameters": [
                    {
                        "TILEMATRIXSET": "2km",
                        "FORMAT": "image/png"
                    }
                ]
            },
            {
                "name": "Layer_02",
                "serviceUrl": "https://gibs.earthdata.nasa.gov/link/to/Layer_02",
                "serviceTypeId": "Layer_02_ID",
                "parameters": [
                    {
                        "TILEMATRIXSET": "2km",
                        "FORMAT": "image/png"
                    }
                ]
            }]
        }]
    }
    
    result = tool.get_events(endpoint="layers", params={}, event_id="", category="")

    assert result["status"] == expected["status"]
    assert result["title"] == expected["title"]
    assert result["description"] == expected["description"]
    assert result["link"] == expected["link"]
    assert result["type"] == expected["type"]
    assert result["events"] == expected["events"]
    assert result["features"] == expected["features"]
    assert result["categories"] == expected["categories"]
    mock_layers_endpoint.assert_called_once_with("")
    

def test_get_events_layers_returns_error_for_fake_category(mock_layers_endpoint: MagicMock) -> None:
    """Test that get_events returns an error if a fake category is given (for layers endpoint)."""
    tool = _load_tool()

    mock_layers_endpoint.side_effect=EONETError(f"Failed to fetch layers for category 'fakecategory' from EONET: {ANY}")
    
    with pytest.raises(ToolError) as e:
        results = tool.get_events(endpoint="layers", params={}, event_id="", category="fakecategory")
    
    assert "Failed to fetch layers for category 'fakecategory'" in str(e.value)
