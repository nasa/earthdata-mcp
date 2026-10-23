"""Tests for the get_events MCP tool."""

import importlib
import types
from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from models.tools.cmr_search import SearchStatus
from models.tools.get_events import (
    GetEventsInput,
    GetEventsOutput,
    EventResult,
    GeoJSONResult,
    CategoryResult,
    LayerResult,
)
from util.eonet.client import EONET_BASE_URL


def _load_tool() -> types.ModuleType:
    """Load the tool module dynamically to avoid circular imports."""
    return importlib.import_module("tools.get_events.tool")


@pytest.fixture
def mock_events_endpoint() -> Generator[MagicMock]:
    """Mock util.eonet.client.events."""
    with patch("util.eonet.client.events") as mock_events:
        yield mock_events

@pytest.fixture
def mock_categories_endpoint() -> Generator[MagicMock]:
    """Mock util.eonet.client.categories."""
    with patch("util.eonet.client.categories") as mock_categories:
        yield mock_categories

@pytest.fixture
def mock_layers_endpoint() -> Generator[MagicMock]:
    """Mock util.eonet.client.layers."""
    with patch("util.eonet.client.layers") as mock_layers:
        yield mock_layers

def test_get_events_returns_event(mock_events_endpoint: MagicMock) -> None:
    """Test that get_events returns an event successfully."""
    tool = _load_tool()

    mock_events_endpoint.return_value = {
        "title": "EONET Event",
        "description": "Natural event from EONET.",
        "link": f"{EONET_BASE_URL}/events",
        "type": "",
        "events": [EventResult(
            id="exampleEvent",
            title="Event Title",
            description="Event description",
            link=f"{EONET_BASE_URL}/events/exampleEvent",
            closed=None,
            categories=[],
            sources=[],
            geometry=[],
        )],
        "features": [],
        "categories": [],
    }

    params = {"limit": "1"}

    result = tool.events(params, False)

    assert result["title"] == "EONET Event"
    assert result["description"] == "Natural event from EONET."
    assert result["link"] == f"{EONET_BASE_URL}/events"
    assert result["type"] == ""
    assert result["events"] == [EventResult(
                                    id="exampleEvent",
                                    title="Event Title",
                                    description="Event description",
                                    link=f"{EONET_BASE_URL}/events/exampleEvent",
                                    closed=None,
                                    categories=[],
                                    sources=[],
                                    geometry=[],
                                )]
    assert result["features"] == []
    assert result["categories"] == []
    mock_events_endpoint.assert_called_once_with(params, False)

def test_get_events_returns_multiple_events(mock_events_endpoint: MagicMock) -> None:
    """Test that get_events returns multiple results successfully."""
    tool = _load_tool()
    
    mock_events_endpoint.return_value = {
        "title": "EONET Event",
        "description": "Natural events from EONET.",
        "link": f"{EONET_BASE_URL}/events",
        "type": "",
        "events": [EventResult(
            id="exampleEvent",
            title="Event Title",
            description="Event description",
            link=f"{EONET_BASE_URL}/events/exampleEvent",
            closed=None,
            categories=[],
            sources=[],
            geometry=[],
        ),
        EventResult(
            id="exampleEvent2",
            title="Event2 Title",
            description="Event2 description",
            link=f"{EONET_BASE_URL}/events/exampleEvent2",
            closed=None,
            categories=[],
            sources=[],
            geometry=[],
        )],
        "features": [],
        "categories": [],
    }

    params = {"limit": "2"}
    
    result = tool.events(params, False)
    
    assert result["title"] == "EONET Event"
    assert result["description"] == "Natural events from EONET."
    assert result["link"] == f"{EONET_BASE_URL}/events"
    assert result["type"] == ""
    assert result["events"] == [EventResult(
                                    id="exampleEvent",
                                    title="Event Title",
                                    description="Event description",
                                    link=f"{EONET_BASE_URL}/events/exampleEvent",
                                    closed=None,
                                    categories=[],
                                    sources=[],
                                    geometry=[],
                                ),
                                EventResult(
                                    id="exampleEvent2",
                                    title="Event2 Title",
                                    description="Event2 description",
                                    link=f"{EONET_BASE_URL}/events/exampleEvent2",
                                    closed=None,
                                    categories=[],
                                    sources=[],
                                    geometry=[],
                                )]
    assert result["features"] == []
    assert result["categories"] == []
    mock_events_endpoint.assert_called_once_with(params, False)

def test_get_events_returns_no_events(mock_events_endpoint: MagicMock) -> None:
    """Test that get_events can return no results successfully."""
    tool = _load_tool()
        
    mock_events_endpoint.return_value = {
        "title": "EONET Events",
        "description": "Natural events from EONET.",
        "link": f"{EONET_BASE_URL}/events",
        "type": "",
        "events": [],
        "features": [],
        "categories": [],
    }

    params = {"limit": "1"}
        
    result = tool.events(params, False)
    
    assert result["title"] == "EONET Events"
    assert result["description"] == "Natural events from EONET."
    assert result["link"] == f"{EONET_BASE_URL}/events"
    assert result["type"] == ""
    assert result["events"] == []
    assert result["features"] == []
    assert result["categories"] == []
    mock_events_endpoint.assert_called_once_with(params, False)

def test_get_events_call_failed(mock_events_endpoint: MagicMock) -> None:
    """Test that get_events returns all results if an invalid EONET request is made."""
    tool = _load_tool()
            
    mock_events_endpoint.return_value = {
        "title": "EONET Event",
        "description": "Natural events from EONET.",
        "link": f"{EONET_BASE_URL}/events",
        "type": "",
        "events": [EventResult(
            id="exampleEvent",
            title="Event Title",
            description="Event description",
            link=f"{EONET_BASE_URL}/events/exampleEvent",
            closed=None,
            categories=[],
            sources=[],
            geometry=[],
        ),
        EventResult(
            id="exampleEvent2",
            title="Event2 Title",
            description="Event2 description",
            link=f"{EONET_BASE_URL}/events/exampleEvent2",
            closed=None,
            categories=[],
            sources=[],
            geometry=[],
        )],
        "features": [],
        "categories": [],
    }
    
    params = {"limit": "-1"}
            
    result = tool.events(params, False)
    
    assert result["title"] == "EONET Event"
    assert result["description"] == "Natural events from EONET."
    assert result["link"] == f"{EONET_BASE_URL}/events"
    assert result["type"] == ""
    assert result["events"] == [EventResult(
                                    id="exampleEvent",
                                    title="Event Title",
                                    description="Event description",
                                    link=f"{EONET_BASE_URL}/events/exampleEvent",
                                    closed=None,
                                    categories=[],
                                    sources=[],
                                    geometry=[],
                                ),
                                EventResult(
                                    id="exampleEvent2",
                                    title="Event2 Title",
                                    description="Event2 description",
                                    link=f"{EONET_BASE_URL}/events/exampleEvent2",
                                    closed=None,
                                    categories=[],
                                    sources=[],
                                    geometry=[],
                                )]
    assert result["features"] == []
    assert result["categories"] == []
    mock_events_endpoint.assert_called_once_with(params, False)

def test_get_events_returns_event_geojson(mock_events_endpoint: MagicMock) -> None:
    """Test that get_events can return a geojson result successfully."""
    tool = _load_tool()
                
    mock_events_endpoint.return_value = {
        "title": "",
        "description": "",
        "link": "",
        "type": "FeatureCollection",
        "events": [],
        "features": [GeoJSONResult(
                type="Feature",
                geometry={
                  "type": "Point",
                  "coordinates": [0.0, 0.0] 
                },
                properties={
                  "name": "A Cool Place",
                  "location": "Anytown, USA"
                }
            )
        ],
        "categories": [],
    }

    params = {"limit": "1"}

    result = tool.events(params, True)

    assert result["title"] == ""
    assert result["description"] == ""
    assert result["link"] == ""
    assert result["type"] == "FeatureCollection"
    assert result["events"] == []
    assert result["features"] == [GeoJSONResult(
                                        type="Feature",
                                        geometry={
                                          "type": "Point",
                                          "coordinates": [0.0, 0.0] 
                                        },
                                        properties={
                                          "name": "A Cool Place",
                                          "location": "Anytown, USA"
                                        }
                                    )
                                ]
    assert result["categories"] == []
    mock_events_endpoint.assert_called_once_with(params, True)

def test_get_events_returns_multiple_events_geojson(mock_events_endpoint: MagicMock) -> None:
    """Test that get_events can return multiple geojson results successfully."""
    tool = _load_tool()
                    
    mock_events_endpoint.return_value = {
        "title": "",
        "description": "",
        "link": "",
        "type": "FeatureCollection",
        "events": [],
        "features": [GeoJSONResult(
                type="Feature",
                geometry={
                  "type": "Point",
                  "coordinates": [0.0, 0.0] 
                },
                properties={
                  "name": "A Cool Place",
                  "location": "Anytown, USA"
                }
            ),
            GeoJSONResult(
                type="Feature",
                geometry={
                  "type": "Point",
                  "coordinates": [1.0, 1.0] 
                },
                properties={
                  "name": "Another Cool Place",
                  "location": "Anothertown, USA"
                }
            )
        ],
        "categories": [],
    }

    params = {"limit": "2"}

    result = tool.events(params, True)

    assert result["title"] == ""
    assert result["description"] == ""
    assert result["link"] == ""
    assert result["type"] == "FeatureCollection"
    assert result["events"] == []
    assert result["features"] == [GeoJSONResult(
                                        type="Feature",
                                        geometry={
                                          "type": "Point",
                                          "coordinates": [0.0, 0.0] 
                                        },
                                        properties={
                                          "name": "A Cool Place",
                                          "location": "Anytown, USA"
                                        }
                                    ),
                                    GeoJSONResult(
                                        type="Feature",
                                        geometry={
                                          "type": "Point",
                                          "coordinates": [1.0, 1.0] 
                                        },
                                        properties={
                                          "name": "Another Cool Place",
                                          "location": "Anothertown, USA"
                                        }
                                    )
                                ]
    assert result["categories"] == []
    mock_events_endpoint.assert_called_once_with(params, True)

def test_get_events_returns_no_events_geojson(mock_events_endpoint: MagicMock) -> None:
    """Test that get_events can return no geojson results successfully."""
    tool = _load_tool()
                        
    mock_events_endpoint.return_value = {
        "title": "",
        "description": "",
        "link": "",
        "type": "FeatureCollection",
        "events": [],
        "features": [],
        "categories": [], 
    }

    params = {"limit": "1"}

    result = tool.events(params, True)

    assert result["title"] == ""
    assert result["description"] == ""
    assert result["link"] == ""    
    assert result["type"] == "FeatureCollection"
    assert result["events"] == []
    assert result["features"] == []
    assert result["categories"] == []    
    mock_events_endpoint.assert_called_once_with(params, True)

def test_events_geojson_return_failed(self, monkeypatch):
    """Test that events returns all results if an invalid geojson request is made."""
    expected = {
        "type": "FeatureCollection",
        "features": [
            {
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
            }
        ]
    }
    
    mock_get = Mock(return_value=_make_response(json_data=expected))
    monkeypatch.setattr("util.eonet.client.requests.get", mock_get)
    
    params = {"limit": "-1"}
    
    result = events(params, True)
    assert result == expected

def test_events_returns_all_events_for_fake_category(self, monkeypatch):
    """Test that events returns all events if a fake category is given."""
    expected = {
        "title": "EONET Event",
        "description": "Natural events from EONET.",
        "link": f"{EONET_BASE_URL}/events",
        "events": [{ "id": "exampleEvent1" }, { "id": "exampleEvent2" }]
    }

    mock_get = Mock(return_value=_make_response(json_data=expected))
    monkeypatch.setattr("util.eonet.client.requests.get", mock_get)

    params = {"category": "fakecategory"}

    result = events(params, False)
    assert result == expected

def test_returns_event_from_category(self, monkeypatch):
    """Test that categories returns events from the specified category."""
    expected = {
        "title": "EONET Events: Category",
        "description": "Category description.",
        "link": f"{EONET_BASE_URL}/categories/categoryId",
        "events": [
            { 
                "id": "exampleEvent",
                "categories": [
                    {
                        "id": "categoryId",
                        "title": "Category Title"
                    }
                ]
            }
        ]
    }
    
    mock_get = Mock(return_value=_make_response(json_data=expected))
    monkeypatch.setattr("util.eonet.client.requests.get", mock_get)

    params = {"limit": "1"}

    result = categories("categoryId", params)
    assert result == expected

def test_returns_multiple_events_from_category(self, monkeypatch):
    """Test that categories returns multiple events from the specified category."""
    expected = {
        "title": "EONET Events: Category",
        "description": "Category description.",
        "link": f"{EONET_BASE_URL}/categories/categoryId",
        "events": [
            { 
                "id": "exampleEvent1",
                "categories": [
                    {
                        "id": "categoryId",
                        "title": "Category Title"
                    }
                ]
            },
            { 
                "id": "exampleEvent2",
                "categories": [
                    {
                        "id": "categoryId",
                        "title": "Category Title"
                    }
                ]
            }
        ]
    }
    
    mock_get = Mock(return_value=_make_response(json_data=expected))
    monkeypatch.setattr("util.eonet.client.requests.get", mock_get)

    params = {"limit": "2"}

    result = categories("categoryId", params)
    assert result == expected

def test_returns_no_events_from_category(self, monkeypatch):
    """Test that categories returns no events for a category without events."""
    expected = {
        "title": ANY,
        "description": ANY,
        "link": f"{EONET_BASE_URL}/categories/categoryId",
        "events": []
    }
    
    mock_get = Mock(return_value=_make_response(json_data=expected))
    monkeypatch.setattr("util.eonet.client.requests.get", mock_get)

    params = {"limit": "1"}

    result = categories("categoryId", params)
    assert result == expected

def test_returns_all_categories(self, monkeypatch):
    """
    Test that categories returns all categories if just the category 
    endpoint itself is passed via the request.
    """
    expected = {
        "title": "EONET Event Categories",
        "description": "List of all the available event categories in the EONET system",
        "link": f"{EONET_BASE_URL}/categories",
        "categories": [
            {
                "id": "cat_01",
                "title": "category1",
                "link": f"{EONET_BASE_URL}/categories/cat_01",
                "description": "Category 1 description.",
                "layers": f"{EONET_BASE_URL}/layers/cat_01_layers"
            },
            {
                "id": "cat_02",
                "title": "category2",
                "link": f"{EONET_BASE_URL}/categories/cat_02",
                "description": "Category 2 description.",
                "layers": f"{EONET_BASE_URL}/layers/cat_02_layers"
            }
        ]
    }
    
    mock_get = Mock(return_value=_make_response(json_data=expected))
    monkeypatch.setattr("util.eonet.client.requests.get", mock_get)
    
    result = categories("", {})
    assert result == expected

def test_returns_all_events_for_category(self, monkeypatch):
    """
    Test that categories returns all events for a given category if just the category's
    endpint is called without any parameters, or with an invalid parameter.
    """
    expected = {
        "title": "EONET Events: Category Title",
        "description": "Category description.",
        "link": f"{EONET_BASE_URL}/categories/categoryId",
        "events": [
            { 
                "id": "exampleEvent1",
                "categories": [
                    {
                        "id": "categoryId",
                        "title": "Category Title"
                    }
                ]
            },
            { 
                "id": "exampleEvent2",
                "categories": [
                    {
                        "id": "categoryId",
                        "title": "Category Title"
                    }
                ]
            }
        ]
    }
    
    mock_get = Mock(return_value=_make_response(json_data=expected))
    monkeypatch.setattr("util.eonet.client.requests.get", mock_get)
    
    result_no_params = categories("wildfires", {})
    result_invalid_param = categories("wildfires", {"limit": "-1"})
    assert result_no_params == expected
    assert result_invalid_param == expected

def test_returns_error_for_fake_category(self, monkeypatch):
    """Test that categories returns an error for a fake category."""
    mock_get = Mock(side_effect=EONETError("That category doesn't exist."))
    monkeypatch.setattr("util.eonet.client.requests.get", mock_get)

    with pytest.raises(EONETError) as e:
        categories("fakecategory", {})
    
    assert "That category doesn't exist." in str(e.value)

def test_returns_layer_from_category(self, monkeypatch):
    """Test that layers can return a single layer from the specified category."""
    expected = {
        "title": "EONET Web Service Layers",
        "description": "List of web service layers in the EONET system.",
        "link": f"{EONET_BASE_URL}/layers/categoryId",
        "categories": [
            { 
                "id": "categoryId",
                "title": "Category Title",
                "layers": [
                    {
                        "name": "layerName",
                        "serviceUrl": "https://www.layer-service.com",
                        "serviceTypeId": "typeId",
                        "parameters": [
                            {
                                "param1": "value1",
                                "param2": "value2"
                            }
                        ]
                    }
                ]
            }
        ]
    }
    
    mock_get = Mock(return_value=_make_response(json_data=expected))
    monkeypatch.setattr("util.eonet.client.requests.get", mock_get)
    
    result = layers("categoryId")
    assert result == expected

def test_returns_multiple_layers_from_category(self, monkeypatch):
    """Test that layers returns multiple layers from the specified category."""
    expected = {
        "title": "EONET Web Service Layers",
        "description": "List of web service layers in the EONET system.",
        "link": f"{EONET_BASE_URL}/layers/categoryId",
        "categories": [
            { 
                "id": "categoryId",
                "title": "Category Title",
                "layers": [
                    {
                        "name": "layer1Name",
                        "serviceUrl": "https://www.layer1-service.com",
                        "serviceTypeId": "typeId1",
                        "parameters": [
                            {
                                "layer1Param1": "layer1Value1",
                                "layer1Param2": "layer1Value2"
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
                    }
                ]
            }
        ]
    }
    
    mock_get = Mock(return_value=_make_response(json_data=expected))
    monkeypatch.setattr("util.eonet.client.requests.get", mock_get)
    
    result = layers("categoryId")
    assert result == expected

def test_returns_no_layers_from_category(self, monkeypatch):
    """Test that layers returns no layers for a category without layers."""
    expected = {
        "title": ANY,
        "description": ANY,
        "link": f"{EONET_BASE_URL}/layers/categoryId",
        "categories": [
            { 
                "id": ANY,
                "title": ANY,
                "layers": []
            }
        ]
    }
    
    mock_get = Mock(return_value=_make_response(json_data=expected))
    monkeypatch.setattr("util.eonet.client.requests.get", mock_get)
    
    result = layers("categoryId")
    assert result == expected

def test_returns_all_layers(self, monkeypatch):
    """Test that layers returns all layers when no category is given."""
    expected = {
        "title": "EONET Web Service Layers",
        "description": "List of web service layers in the EONET system",
        "link": f"{EONET_BASE_URL}/layers",
        "categories": [
            {
                "layers": [
                    {
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
                    }
                ]
            }
        ]
    }
    
    mock_get = Mock(return_value=_make_response(json_data=expected))
    monkeypatch.setattr("util.eonet.client.requests.get", mock_get)
    
    result = layers("categoryId")
    assert result == expected

def test_layers_returns_error_for_fake_category(self, monkeypatch):
    """Test that layers returns an error if a fake category is given."""
    mock_get = Mock(side_effect=EONETError("That category doesn't exist."))
    monkeypatch.setattr("util.eonet.client.requests.get", mock_get)

    with pytest.raises(EONETError) as e:
        layers("fakecategory")

    assert "That category doesn't exist." in str(e.value)