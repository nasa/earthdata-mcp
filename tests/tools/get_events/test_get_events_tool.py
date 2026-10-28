"""Tests for the get_events MCP tool."""

import importlib
import types
from collections.abc import Generator
from unittest.mock import MagicMock, patch, ANY

import pytest

from models.tools.cmr_search import SearchStatus
from models.tools.get_events import (
    EventResult,
    GeoJSONResult,
    GetEventsOutput,
    CategoryResult,
    LayerResult,
)
from util.eonet.client import (
    EONET_BASE_URL, 
    EONETError,
    get_request_url,
)


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

@pytest.fixture
def mock_get_events() -> Generator[MagicMock]:
    """Mock tools.get_events.tool.get_events"""
    with patch("tools.get_events.tool.get_events") as mock_get_events:
        yield mock_get_events


def test_get_events_returns_event(mock_events_endpoint: MagicMock, mock_get_events: MagicMock) -> None:
    """Test that get_events returns an event successfully."""
    tool = _load_tool()

    mock_events_endpoint.return_value = {
        "title": "EONET Event",
        "description": "Natural event from EONET.",
        "link": f"{EONET_BASE_URL}/events",
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
    }

    mock_get_events.return_value = GetEventsOutput(
        status=SearchStatus.SUCCESS,
        title="EONET Event",
        description="Natural event from EONET.",
        link=f"{EONET_BASE_URL}/events",
        type="",
        events=[EventResult(
            id="exampleEvent",
            title="Event Title",
            description="Event description",
            link=f"{EONET_BASE_URL}/events/exampleEvent",
            closed=None,
            categories=[],
            sources=[],
            geometry=[],
        )],
        features=[],
        categories=[],
    )

    params = {"limit": "1"}

    result = tool.get_events(endpoint="events", params=params, category="")

    assert result.status == SearchStatus.SUCCESS
    assert result.title == "EONET Event"
    assert result.description == "Natural event from EONET."
    assert result.link == f"{EONET_BASE_URL}/events"
    assert result.type == ""
    assert result.events == [EventResult(
            id="exampleEvent",
            title="Event Title",
            description="Event description",
            link=f"{EONET_BASE_URL}/events/exampleEvent",
            closed=None,
            categories=[],
            sources=[],
            geometry=[],
        )
    ]
    assert result.features == []
    assert result.categories == []
    mock_get_events.assert_called_once_with(endpoint="events", params=params, category="")


def test_get_events_returns_multiple_events(mock_events_endpoint: MagicMock, mock_get_events: MagicMock) -> None:
    """Test that get_events returns multiple results successfully."""
    tool = _load_tool()
    
    mock_events_endpoint.return_value = {
        "title": "EONET Event",
        "description": "Natural events from EONET.",
        "link": f"{EONET_BASE_URL}/events",
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
    }

    mock_get_events.return_value = GetEventsOutput(
        status=SearchStatus.SUCCESS,
        title="EONET Event",
        description="Natural events from EONET.",
        link=f"{EONET_BASE_URL}/events",
        type="",
        events=[EventResult(
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
        features=[],
        categories=[],
    )

    params = {"limit": "2"}
    
    result = tool.get_events(endpoint="events", params=params, category="")

    assert result.status == SearchStatus.SUCCESS
    assert result.title == "EONET Event"
    assert result.description == "Natural events from EONET."
    assert result.link == f"{EONET_BASE_URL}/events"
    assert result.type == ""
    assert result.events == [EventResult(
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
        )
    ]
    assert result.features == []
    assert result.categories == []
    mock_get_events.assert_called_once_with(endpoint="events", params=params, category="")


def test_get_events_returns_no_events(mock_events_endpoint: MagicMock, mock_get_events: MagicMock) -> None:
    """Test that get_events can return no results successfully."""
    tool = _load_tool()
        
    mock_events_endpoint.return_value = {
        "title": "EONET Events",
        "description": "Natural events from EONET.",
        "link": f"{EONET_BASE_URL}/events",
        "events": [],
    }

    mock_get_events.return_value = GetEventsOutput(
        status=SearchStatus.NO_RESULTS,
        title="EONET Events",
        description="Natural events from EONET.",
        link=f"{EONET_BASE_URL}/events",
        type="",
        events=[],
        features=[],
        categories=[],
    )

    params = {"limit": "1"}
        
    result = tool.get_events(endpoint="events", params=params, category="")

    assert result.status == SearchStatus.NO_RESULTS
    assert result.title == "EONET Events"
    assert result.description == "Natural events from EONET."
    assert result.link == f"{EONET_BASE_URL}/events"
    assert result.type == ""
    assert result.events == []
    assert result.features == []
    assert result.categories == []
    mock_get_events.assert_called_once_with(endpoint="events", params=params, category="")


def test_get_events_call_failed(mock_events_endpoint: MagicMock, mock_get_events: MagicMock) -> None:
    """Test that get_events returns all results if an invalid EONET request is made."""
    tool = _load_tool()
            
    mock_events_endpoint.return_value = {
        "title": "EONET Event",
        "description": "Natural events from EONET.",
        "link": f"{EONET_BASE_URL}/events",
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
    }

    mock_get_events.return_value = GetEventsOutput(
        status=SearchStatus.SUCCESS,
        title="EONET Event",
        description="Natural events from EONET.",
        link=f"{EONET_BASE_URL}/events",
        type="",
        events=[EventResult(
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
        features=[],
        categories=[],
    )
    
    params = {"limit": "-1"}
            
    result = tool.get_events(endpoint="events", params=params, category="")

    assert result.status == SearchStatus.SUCCESS
    assert result.title == "EONET Event"
    assert result.description == "Natural events from EONET."
    assert result.link == f"{EONET_BASE_URL}/events"
    assert result.type == ""
    assert result.events == [EventResult(
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
        )
    ]
    assert result.features == []
    assert result.categories == []
    mock_get_events.assert_called_once_with(endpoint="events", params=params, category="")


def test_get_events_returns_event_geojson(mock_events_endpoint: MagicMock, mock_get_events: MagicMock) -> None:
    """Test that get_events can return a geojson result successfully."""
    tool = _load_tool()
                
    mock_events_endpoint.return_value = {
        "type": "FeatureCollection",
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
    }

    mock_get_events.return_value = GetEventsOutput(
        status=SearchStatus.SUCCESS,
        title="",
        description="",
        link="",
        type="FeatureCollection",
        events=[],
        features=[GeoJSONResult(
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
        categories=[],
    )

    params = {"limit": "1"}

    result = tool.get_events(endpoint="events/geojson", params=params, category="")

    assert result.status == SearchStatus.SUCCESS
    assert result.title == ""
    assert result.description == ""
    assert result.link == ""
    assert result.type == "FeatureCollection"
    assert result.events == []
    assert result.features == [GeoJSONResult(
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
    assert result.categories == []
    mock_get_events.assert_called_once_with(endpoint="events/geojson", params=params, category="")


def test_get_events_returns_multiple_events_geojson(mock_events_endpoint: MagicMock, mock_get_events: MagicMock) -> None:
    """Test that get_events can return multiple geojson results successfully."""
    tool = _load_tool()
                    
    mock_events_endpoint.return_value = {
        "type": "FeatureCollection",
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
    }

    mock_get_events.return_value = GetEventsOutput(
        status=SearchStatus.SUCCESS,
        title="",
        description="",
        link="",
        type="FeatureCollection",
        events=[],
        features=[GeoJSONResult(
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
        categories=[],
    )

    params = {"limit": "2"}

    result = tool.get_events(endpoint="events/geojson", params=params, category="")

    assert result.status == SearchStatus.SUCCESS
    assert result.title == ""
    assert result.description == ""
    assert result.link == ""
    assert result.type == "FeatureCollection"
    assert result.events == []
    assert result.features == [GeoJSONResult(
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
    assert result.categories == []
    mock_get_events.assert_called_once_with(endpoint="events/geojson", params=params, category="")


def test_get_events_returns_no_events_geojson(mock_events_endpoint: MagicMock, mock_get_events: MagicMock) -> None:
    """Test that get_events can return no geojson results successfully."""
    tool = _load_tool()
                        
    mock_events_endpoint.return_value = {
        "type": "FeatureCollection",
        "features": [],
    }

    mock_get_events.return_value = GetEventsOutput(
        status=SearchStatus.NO_RESULTS,
        title="",
        description="",
        link="",
        type="FeatureCollection",
        events=[],
        features=[],
        categories=[], 
    )

    params = {"limit": "1"}

    result = tool.get_events(endpoint="events/geojson", params=params, category="")

    assert result.status == SearchStatus.NO_RESULTS
    assert result.title == ""
    assert result.description == ""
    assert result.link == ""    
    assert result.type == "FeatureCollection"
    assert result.events == []
    assert result.features == []
    assert result.categories == []    
    mock_get_events.assert_called_once_with(endpoint="events/geojson", params=params, category="")


def test_get_events_geojson_return_failed(mock_events_endpoint: MagicMock, mock_get_events: MagicMock) -> None:
    """Test that get_events returns all results if an invalid geojson request is made."""
    tool = _load_tool()
                            
    mock_events_endpoint.return_value = {
        "type": "FeatureCollection",
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
    }

    mock_get_events.return_value = GetEventsOutput(
        status=SearchStatus.SUCCESS,
        title="",
        description="",
        link="",
        type="FeatureCollection",
        events=[],
        features=[GeoJSONResult(
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
        categories=[],
    )
    
    params = {"limit": "-1"}
    
    result = tool.get_events(endpoint="events/geojson", params=params, category="")

    assert result.status == SearchStatus.SUCCESS
    assert result.title == ""
    assert result.description == ""
    assert result.link == ""    
    assert result.type == "FeatureCollection"
    assert result.events == []
    assert result.features == [GeoJSONResult(
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
    assert result.categories == []    
    mock_get_events.assert_called_once_with(endpoint="events/geojson", params=params, category="")


def test_get_events_returns_all_events_for_fake_category(mock_events_endpoint: MagicMock, mock_get_events: MagicMock) -> None:
    """Test that get_events returns all events if a fake category is given."""
    tool = _load_tool()
                                
    mock_events_endpoint.return_value = {
        "title": "EONET Event",
        "description": "Natural events from EONET.",
        "link": f"{EONET_BASE_URL}/events",
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
            )
        ],
    }

    mock_get_events.return_value = GetEventsOutput(
        status=SearchStatus.SUCCESS,
        title="EONET Event",
        description="Natural events from EONET.",
        link=f"{EONET_BASE_URL}/events",
        type="",
        events=[EventResult(
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
            )
        ],
        features=[],
        categories=[],
    )

    params = {"category": "fakecategory"}

    result = tool.get_events(endpoint="events", params=params, category="")

    assert result.status == SearchStatus.SUCCESS
    assert result.title == "EONET Event"
    assert result.description == "Natural events from EONET."
    assert result.link == f"{EONET_BASE_URL}/events"    
    assert result.type == ""
    assert result.events == [EventResult(
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
        )
    ]
    assert result.features == []
    assert result.categories == []    
    mock_get_events.assert_called_once_with(endpoint="events", params=params, category="")


def test_get_events_returns_event_from_category(mock_categories_endpoint: MagicMock, mock_get_events: MagicMock) -> None:
    """Test that get_events returns events from the specified category."""
    tool = _load_tool()
                                    
    mock_categories_endpoint.return_value = {
        "title": "EONET Events: Category",
        "description": "Category description.",
        "link": f"{EONET_BASE_URL}/categories/categoryId",
        "events": [EventResult(
                id="exampleEvent",
                title="Event Title",
                description="Event description",
                link=f"{EONET_BASE_URL}/events/exampleEvent",
                closed=None,
                categories=[CategoryResult(
                    id="categoryId",
                    title="Category Title",
                )],
                sources=[],
                geometry=[],
            )
        ],
    }

    mock_get_events.return_value = GetEventsOutput(
        status=SearchStatus.SUCCESS,
        title="EONET Events: Category",
        description="Category description.",
        link=f"{EONET_BASE_URL}/categories/categoryId",
        type="",
        events=[EventResult(
                id="exampleEvent",
                title="Event Title",
                description="Event description",
                link=f"{EONET_BASE_URL}/events/exampleEvent",
                closed=None,
                categories=[CategoryResult(
                    id="categoryId",
                    title="Category Title",
                )],
                sources=[],
                geometry=[],
            )
        ],
        features=[],
        categories=[],
    )

    params = {"limit": "1"}

    result = tool.get_events(endpoint="categories", params=params, category="categoryId")

    assert result.status == SearchStatus.SUCCESS
    assert result.title == "EONET Events: Category"
    assert result.description == "Category description."
    assert result.link == f"{EONET_BASE_URL}/categories/categoryId"    
    assert result.type == ""
    assert result.events == [EventResult(
            id="exampleEvent",
            title="Event Title",
            description="Event description",
            link=f"{EONET_BASE_URL}/events/exampleEvent",
            closed=None,
            categories=[CategoryResult(
                id="categoryId",
                title="Category Title",
            )],
            sources=[],
            geometry=[],
        )
    ]
    assert result.features == []
    assert result.categories == []    
    mock_get_events.assert_called_once_with(endpoint="categories", params=params, category="categoryId")


def test_get_events_returns_multiple_events_from_category(mock_categories_endpoint: MagicMock, mock_get_events: MagicMock) -> None:
    """Test that get_events returns multiple events from the specified category."""
    tool = _load_tool()
                                        
    mock_categories_endpoint.return_value = {
        "title": "EONET Events: Category",
        "description": "Category description.",
        "link": f"{EONET_BASE_URL}/categories/categoryId",
        "events": [EventResult(
                id="exampleEvent",
                title="Event Title",
                description="Event description",
                link=f"{EONET_BASE_URL}/events/exampleEvent",
                closed=None,
                categories=[CategoryResult(
                    id="categoryId",
                    title="Category Title",
                )],
                sources=[],
                geometry=[],
            ),
            EventResult(
                id="exampleEvent2",
                title="Event2 Title",
                description="Event2 description",
                link=f"{EONET_BASE_URL}/events/exampleEvent2",
                closed=None,
                categories=[CategoryResult(
                    id="categoryId",
                    title="Category Title",
                )],
                sources=[],
                geometry=[],
            )
        ],
    }

    mock_get_events.return_value = GetEventsOutput(
        status=SearchStatus.SUCCESS,
        title="EONET Events: Category",
        description="Category description.",
        link=f"{EONET_BASE_URL}/categories/categoryId",
        type="",
        events=[EventResult(
                id="exampleEvent",
                title="Event Title",
                description="Event description",
                link=f"{EONET_BASE_URL}/events/exampleEvent",
                closed=None,
                categories=[CategoryResult(
                    id="categoryId",
                    title="Category Title",
                )],
                sources=[],
                geometry=[],
            ),
            EventResult(
                id="exampleEvent2",
                title="Event2 Title",
                description="Event2 description",
                link=f"{EONET_BASE_URL}/events/exampleEvent2",
                closed=None,
                categories=[CategoryResult(
                    id="categoryId",
                    title="Category Title",
                )],
                sources=[],
                geometry=[],
            )
        ],
        features=[],
        categories=[],
    )

    params = {"limit": "2"}

    result = tool.get_events(endpoint="categories", params=params, category="categoryId")

    assert result.status == SearchStatus.SUCCESS
    assert result.title == "EONET Events: Category"
    assert result.description == "Category description."
    assert result.link == f"{EONET_BASE_URL}/categories/categoryId"    
    assert result.type == ""
    assert result.events == [EventResult(
            id="exampleEvent",
            title="Event Title",
            description="Event description",
            link=f"{EONET_BASE_URL}/events/exampleEvent",
            closed=None,
            categories=[CategoryResult(
                id="categoryId",
                title="Category Title",
            )],
            sources=[],
            geometry=[],
        ),
        EventResult(
            id="exampleEvent2",
            title="Event2 Title",
            description="Event2 description",
            link=f"{EONET_BASE_URL}/events/exampleEvent2",
            closed=None,
            categories=[CategoryResult(
                id="categoryId",
                title="Category Title",
            )],
            sources=[],
            geometry=[],
        )
    ]
    assert result.features == []
    assert result.categories == []    
    mock_get_events.assert_called_once_with(endpoint="categories", params=params, category="categoryId")


def test_get_events_returns_no_events_from_category(mock_categories_endpoint: MagicMock, mock_get_events: MagicMock) -> None:
    """Test that get_events returns no events for a category without events."""
    tool = _load_tool()
                                            
    mock_categories_endpoint.return_value = {
        "title": "Category Title",
        "description": "Category description",
        "link": f"{EONET_BASE_URL}/categories/categoryId",
        "events": [],
    }

    mock_get_events.return_value = GetEventsOutput(
        status=SearchStatus.NO_RESULTS,
        title="Category Title",
        description="Category description",
        link=f"{EONET_BASE_URL}/categories/categoryId",
        type="",
        events=[],
        features=[],
        categories=[],
    )

    params = {"limit": "1"}

    result = tool.get_events(endpoint="categories", params=params, category="categoryId")

    assert result.status == SearchStatus.NO_RESULTS
    assert result.title == ANY
    assert result.description == ANY
    assert result.link == f"{EONET_BASE_URL}/categories/categoryId"    
    assert result.type == ""
    assert result.events == []
    assert result.features == []
    assert result.categories == []    
    mock_get_events.assert_called_once_with(endpoint="categories", params=params, category="categoryId")


def test_get_events_returns_all_categories(mock_categories_endpoint: MagicMock, mock_get_events: MagicMock) -> None:
    """
    Test that get_events returns all categories if just the category 
    endpoint itself is passed via the request.
    """
    tool = _load_tool()
                                                
    mock_categories_endpoint.return_value = {
        "title": "EONET Event Categories",
        "description": "List of all the available event categories in the EONET system",
        "link": f"{EONET_BASE_URL}/categories",
        "categories": [CategoryResult(
                id="categoryId",
                title="Category Title",
                link=f"{EONET_BASE_URL}/categories/categoryId",
                description="Category description.",
                layers=f"{EONET_BASE_URL}/layers/categoryId_layers"
            ),
            CategoryResult(
                id="categoryId2",
                title="Category2 Title",
                link=f"{EONET_BASE_URL}/categories/categoryId2",
                description="Category2 description.",
                layers=f"{EONET_BASE_URL}/layers/categoryId2_layers"
            )
        ]
    }

    mock_get_events.return_value = GetEventsOutput(
        status=SearchStatus.SUCCESS,
        title="EONET Event Categories",
        description="List of all the available event categories in the EONET system",
        link=f"{EONET_BASE_URL}/categories",
        type="",
        events=[],
        features=[],
        categories=[CategoryResult(
                id="categoryId",
                title="Category Title",
                link=f"{EONET_BASE_URL}/categories/categoryId",
                description="Category description.",
                layers=f"{EONET_BASE_URL}/layers/categoryId_layers"
            ),
            CategoryResult(
                id="categoryId2",
                title="Category2 Title",
                link=f"{EONET_BASE_URL}/categories/categoryId2",
                description="Category2 description.",
                layers=f"{EONET_BASE_URL}/layers/categoryId2_layers"
            )
        ]
    )
    
    result = tool.get_events(endpoint="categories", params={}, category="")

    assert result.status == SearchStatus.SUCCESS
    assert result.title == "EONET Event Categories"
    assert result.description == "List of all the available event categories in the EONET system"
    assert result.link == f"{EONET_BASE_URL}/categories"
    assert result.type == ""
    assert result.events == []
    assert result.features == []
    assert result.categories == [CategoryResult(
            id="categoryId",
            title="Category Title",
            link=f"{EONET_BASE_URL}/categories/categoryId",
            description="Category description.",
            layers=f"{EONET_BASE_URL}/layers/categoryId_layers"
        ),
        CategoryResult(
            id="categoryId2",
            title="Category2 Title",
            link=f"{EONET_BASE_URL}/categories/categoryId2",
            description="Category2 description.",
            layers=f"{EONET_BASE_URL}/layers/categoryId2_layers"
        )
    ]   
    mock_get_events.assert_called_once_with(endpoint="categories", params={}, category="")


def test_get_events_returns_all_events_for_category_endpoint(mock_categories_endpoint: MagicMock, mock_get_events: MagicMock) -> None   :
    """
    Test that get_events returns all events for a given category if just the category's
    endpoint is called without any parameters.
    """
    tool = _load_tool()
                                                    
    mock_categories_endpoint.return_value = {
        "title": "EONET Events: Category Title",
        "description": "Category description.",
        "link": f"{EONET_BASE_URL}/categories/categoryId",
        "events": [EventResult(
                id="exampleEvent",
                title="Event Title",
                description="Event description",
                link=f"{EONET_BASE_URL}/events/exampleEvent",
                closed=None,
                categories=[CategoryResult(
                    id="categoryId",
                    title="Category Title",
                )],
                sources=[],
                geometry=[],
            ),
            EventResult(
                id="exampleEvent2",
                title="Event2 Title",
                description="Event2 description",
                link=f"{EONET_BASE_URL}/events/exampleEvent2",
                closed=None,
                categories=[CategoryResult(
                    id="categoryId",
                    title="Category Title",
                )],
                sources=[],
                geometry=[],
            )
        ],
    }

    mock_get_events.return_value = GetEventsOutput(
        status=SearchStatus.SUCCESS,
        title="EONET Events: Category Title",
        description="Category description.",
        link=f"{EONET_BASE_URL}/categories/categoryId",
        type="",
        events=[EventResult(
                id="exampleEvent",
                title="Event Title",
                description="Event description",
                link=f"{EONET_BASE_URL}/events/exampleEvent",
                closed=None,
                categories=[CategoryResult(
                    id="categoryId",
                    title="Category Title",
                )],
                sources=[],
                geometry=[],
            ),
            EventResult(
                id="exampleEvent2",
                title="Event2 Title",
                description="Event2 description",
                link=f"{EONET_BASE_URL}/events/exampleEvent2",
                closed=None,
                categories=[CategoryResult(
                    id="categoryId",
                    title="Category Title",
                )],
                sources=[],
                geometry=[],
            )
        ],
        features=[],
        categories=[],
    )
    
    results = tool.get_events(endpoint="categories", params={}, category="categoryId")

    assert results.status == SearchStatus.SUCCESS
    assert results.title == "EONET Events: Category Title"
    assert results.description == "Category description."
    assert results.link == f"{EONET_BASE_URL}/categories/categoryId"
    assert results.type == ""
    assert results.events == [EventResult(
            id="exampleEvent",
            title="Event Title",
            description="Event description",
            link=f"{EONET_BASE_URL}/events/exampleEvent",
            closed=None,
            categories=[CategoryResult(
                id="categoryId",
                title="Category Title",
            )],
            sources=[],
            geometry=[],
        ),
        EventResult(
            id="exampleEvent2",
            title="Event2 Title",
            description="Event2 description",
            link=f"{EONET_BASE_URL}/events/exampleEvent2",
            closed=None,
            categories=[CategoryResult(
                id="categoryId",
                title="Category Title",
            )],
            sources=[],
            geometry=[],
        )
    ]
    assert results.features == []
    assert results.categories == []
    mock_get_events.assert_called_once_with(endpoint="categories", params={}, category="categoryId")


def test_get_events_returns_all_events_for_category_endpoint_invalid_params(mock_categories_endpoint: MagicMock, mock_get_events: MagicMock) -> None   :
    """
    Test that get_events returns all events for a given category if just the category's
    endpoint is called with an invalid parameter.
    """
    tool = _load_tool()
                                                    
    mock_categories_endpoint.return_value = {
        "title": "EONET Events: Category Title",
        "description": "Category description.",
        "link": f"{EONET_BASE_URL}/categories/categoryId",
        "events": [EventResult(
                id="exampleEvent",
                title="Event Title",
                description="Event description",
                link=f"{EONET_BASE_URL}/events/exampleEvent",
                closed=None,
                categories=[CategoryResult(
                    id="categoryId",
                    title="Category Title",
                )],
                sources=[],
                geometry=[],
            ),
            EventResult(
                id="exampleEvent2",
                title="Event2 Title",
                description="Event2 description",
                link=f"{EONET_BASE_URL}/events/exampleEvent2",
                closed=None,
                categories=[CategoryResult(
                    id="categoryId",
                    title="Category Title",
                )],
                sources=[],
                geometry=[],
            )
        ],
    }

    mock_get_events.return_value = GetEventsOutput(
        status=SearchStatus.SUCCESS,
        title="EONET Events: Category Title",
        description="Category description.",
        link=f"{EONET_BASE_URL}/categories/categoryId",
        type="",
        events=[EventResult(
                id="exampleEvent",
                title="Event Title",
                description="Event description",
                link=f"{EONET_BASE_URL}/events/exampleEvent",
                closed=None,
                categories=[CategoryResult(
                    id="categoryId",
                    title="Category Title",
                )],
                sources=[],
                geometry=[],
            ),
            EventResult(
                id="exampleEvent2",
                title="Event2 Title",
                description="Event2 description",
                link=f"{EONET_BASE_URL}/events/exampleEvent2",
                closed=None,
                categories=[CategoryResult(
                    id="categoryId",
                    title="Category Title",
                )],
                sources=[],
                geometry=[],
            )
        ],
        features=[],
        categories=[],
    )

    results = tool.get_events(endpoint="categories", params={ "limit": "-1" }, category="categoryId")

    assert results.status == SearchStatus.SUCCESS
    assert results.title == "EONET Events: Category Title"
    assert results.description == "Category description."
    assert results.link == f"{EONET_BASE_URL}/categories/categoryId"
    assert results.type == ""
    assert results.events == [EventResult(
            id="exampleEvent",
            title="Event Title",
            description="Event description",
            link=f"{EONET_BASE_URL}/events/exampleEvent",
            closed=None,
            categories=[CategoryResult(
                id="categoryId",
                title="Category Title",
            )],
            sources=[],
            geometry=[],
        ),
        EventResult(
            id="exampleEvent2",
            title="Event2 Title",
            description="Event2 description",
            link=f"{EONET_BASE_URL}/events/exampleEvent2",
            closed=None,
            categories=[CategoryResult(
                id="categoryId",
                title="Category Title",
            )],
            sources=[],
            geometry=[],
        )
    ]
    assert results.features == []
    assert results.categories == []
    mock_get_events.assert_called_with(endpoint="categories", params={ "limit": "-1" }, category="categoryId")


def test_get_events_categories_returns_error_for_fake_category(mock_categories_endpoint: MagicMock, mock_get_events: MagicMock) -> None:
    """Test that get_events returns an error for a fake category (for category endpoint)."""
    tool = _load_tool()

    mock_categories_endpoint.side_effect=EONETError("That category doesn't exist.")

    mock_get_events.return_value = GetEventsOutput(
        status=SearchStatus.ERROR,
        error_message=f"{ANY}",
        title=SearchStatus.ERROR,
        description="Failed EONET API request",
        link=f"{get_request_url()}",
        type="",
        events=[],
        features=[],
        categories=[],
    )

    with pytest.raises(EONETError) as e:
        results = tool.get_events(endpoint="categories", params={}, category="fakecategory")

    assert results.status == SearchStatus.ERROR
    assert results.error_message == f"{ANY}"
    assert results.title == SearchStatus.ERROR
    assert results.description == "Failed EONET API request"
    assert results.link == ANY
    assert results.type == ""
    assert results.events == []
    assert results.features == []
    assert results.categories == []
    assert "That category doesn't exist." in str(e.value)
    mock_get_events.assert_called_once_with(endpoint="categories", params={}, category="fakecategory")


def test_get_events_returns_layer_from_category(mock_layers_endpoint: MagicMock, mock_get_events: MagicMock) -> None:
    """Test that get_events can return a single layer from the specified category."""
    tool = _load_tool()

    mock_layers_endpoint.return_value = {
        "title": "EONET Web Service Layers",
        "description": "List of web service layers in the EONET system.",
        "link": f"{EONET_BASE_URL}/layers/categoryId",
        "categories": [CategoryResult(
                id="categoryId",
                title="Category Title",
                layers=[LayerResult(
                        name="layerName",
                        serviceUrl="https://www.layer-service.com",
                        serviceTypeId="typeId",
                        parameters=[
                            {
                                "param1": "value1",
                                "param2": "value2"
                            }
                        ]
                    )
                ]
            )
        ]
    }

    mock_get_events.return_value = GetEventsOutput(
        status=SearchStatus.SUCCESS,
        title="EONET Web Service Layers",
        description="List of web service layers in the EONET system.",
        link=f"{EONET_BASE_URL}/layers/categoryId",
        type="",
        events=[],
        features=[],
        categories=[CategoryResult(
                id="categoryId",
                title="Category Title",
                layers=[LayerResult(
                        name="layerName",
                        serviceUrl="https://www.layer-service.com",
                        serviceTypeId="typeId",
                        parameters=[
                            {
                                "param1": "value1",
                                "param2": "value2"
                            }
                        ]
                    )
                ]
            )
        ]
    )
    
    result = tool.get_events(endpoint="layers", params={}, category="categoryId")

    assert result.status == SearchStatus.SUCCESS
    assert result.title == "EONET Web Service Layers"
    assert result.description == "List of web service layers in the EONET system."
    assert result.link == f"{EONET_BASE_URL}/layers/categoryId"
    assert result.type == ""
    assert result.events == []
    assert result.features == []
    assert result.categories == [CategoryResult(
            id="categoryId",
            title="Category Title",
            layers=[LayerResult(
                    name="layerName",
                    serviceUrl="https://www.layer-service.com",
                    serviceTypeId="typeId",
                    parameters=[
                        {
                            "param1": "value1",
                            "param2": "value2"
                        }
                    ]
                )
            ]
        )
    ]
    mock_get_events.assert_called_once_with(endpoint="layers", params={}, category="categoryId")


def test_get_events_returns_multiple_layers_from_category(mock_layers_endpoint: MagicMock, mock_get_events: MagicMock) -> None:
    """Test that get_events returns multiple layers from the specified category."""
    tool = _load_tool()
    
    mock_layers_endpoint.return_value = {
        "title": "EONET Web Service Layers",
        "description": "List of web service layers in the EONET system.",
        "link": f"{EONET_BASE_URL}/layers/categoryId",
        "categories": [CategoryResult(
                id="categoryId",
                title="Category Title",
                layers=[LayerResult(
                        name="layerName",
                        serviceUrl="https://www.layer-service.com",
                        serviceTypeId="typeId",
                        parameters=[
                            {
                                "layer1param1": "layer1value1",
                                "layer1param2": "layer1value2"
                            }
                        ]
                    ),
                    LayerResult(
                        name="layer2Name",
                        serviceUrl="https://www.layer2-service.com",
                        serviceTypeId="typeId2",
                        parameters=[
                            {
                                "layer2Param1": "layer2Value1",
                                "layer2Param2": "layer2Value2"
                            }
                        ]
                    )
                ]
            )
        ]
    }

    mock_get_events.return_value = GetEventsOutput(
        status=SearchStatus.SUCCESS,
        title="EONET Web Service Layers",
        description="List of web service layers in the EONET system.",
        link=f"{EONET_BASE_URL}/layers/categoryId",
        type="",
        events=[],
        features=[],
        categories=[CategoryResult(
                id="categoryId",
                title="Category Title",
                layers=[LayerResult(
                        name="layerName",
                        serviceUrl="https://www.layer-service.com",
                        serviceTypeId="typeId",
                        parameters=[
                            {
                                "layer1param1": "layer1value1",
                                "layer1param2": "layer1value2"
                            }
                        ]
                    ),
                    LayerResult(
                        name="layer2Name",
                        serviceUrl="https://www.layer2-service.com",
                        serviceTypeId="typeId2",
                        parameters=[
                            {
                                "layer2Param1": "layer2Value1",
                                "layer2Param2": "layer2Value2"
                            }
                        ]
                    )
                ]
            )
        ]
    )
    
    result = tool.get_events(endpoint="layers", params={}, category="categoryId")

    assert result.status == SearchStatus.SUCCESS
    assert result.title == "EONET Web Service Layers"
    assert result.description == "List of web service layers in the EONET system."
    assert result.link == f"{EONET_BASE_URL}/layers/categoryId"
    assert result.type == ""
    assert result.events == []
    assert result.features == []
    assert result.categories == [CategoryResult(
            id="categoryId",
            title="Category Title",
            layers=[LayerResult(
                    name="layerName",
                    serviceUrl="https://www.layer-service.com",
                    serviceTypeId="typeId",
                    parameters=[
                        {
                            "layer1param1": "layer1value1",
                            "layer1param2": "layer1value2"
                        }
                    ]
                ),
                LayerResult(
                    name="layer2Name",
                    serviceUrl="https://www.layer2-service.com",
                    serviceTypeId="typeId2",
                    parameters=[
                        {
                            "layer2Param1": "layer2Value1",
                            "layer2Param2": "layer2Value2"
                        }
                    ]
                )
            ]
        )
    ]
    mock_get_events.assert_called_once_with(endpoint="layers", params={}, category="categoryId")


def test_get_events_returns_no_layers_from_category(mock_layers_endpoint: MagicMock, mock_get_events: MagicMock) -> None:
    """Test that get_events returns no layers for a category without layers."""
    tool = _load_tool()
        
    mock_layers_endpoint.return_value = {
        "title": "EONET Web Service Layers",
        "description": "List of web service layers in the EONET system.",
        "link": f"{EONET_BASE_URL}/layers/categoryId",
        "categories": [CategoryResult(
                id="categoryId",
                title="Category Title",
                layers=[]
            )
        ]
    }

    mock_get_events.return_value = GetEventsOutput(
        status=SearchStatus.NO_RESULTS,
        title="EONET Web Service Layers",
        description="List of web service layers in the EONET system.",
        link=f"{EONET_BASE_URL}/layers/categoryId",
        type="",
        events=[],
        features=[],
        categories=[CategoryResult(
                id="categoryId",
                title="Category Title",
                layers=[]
            )
        ]
    )
    
    result = tool.get_events(endpoint="layers", params={}, category="categoryId")

    assert result.status == SearchStatus.NO_RESULTS
    assert result.title == ANY
    assert result.description == ANY
    assert result.link == f"{EONET_BASE_URL}/layers/categoryId"
    assert result.categories == [CategoryResult(
                                            id="categoryId",
                                            title="Category Title",
                                            layers=[]
                                        )
                                    ]
    mock_get_events.assert_called_once_with(endpoint="layers", params={}, category="categoryId")


def test_get_events_returns_all_layers(mock_layers_endpoint: MagicMock, mock_get_events: MagicMock) -> None:
    """Test that get_events returns all layers when no category is given."""
    tool = _load_tool()
            
    mock_layers_endpoint.return_value = {
        "title": "EONET Web Service Layers",
        "description": "List of web service layers in the EONET system",
        "link": f"{EONET_BASE_URL}/layers",
        "categories": [CategoryResult(
                layers=[LayerResult(
                        name="Layer_01",
                        serviceUrl="https://gibs.earthdata.nasa.gov/link/to/Layer_01",
                        serviceTypeId="Layer_01_ID",
                        parameters=[
                            {
                                "TILEMATRIXSET": "2km",
                                "FORMAT": "image/png"
                            }
                        ]
                    ),
                    LayerResult(
                        name="Layer_02",
                        serviceUrl="https://gibs.earthdata.nasa.gov/link/to/Layer_02",
                        serviceTypeId="Layer_02_ID",
                        parameters=[
                            {
                                "TILEMATRIXSET": "2km",
                                "FORMAT": "image/png"
                            }
                        ]
                    )
                ]
            )
        ]
    }

    mock_get_events.return_value = GetEventsOutput(
        status=SearchStatus.SUCCESS,
        title="EONET Web Service Layers",
        description="List of web service layers in the EONET system",
        link=f"{EONET_BASE_URL}/layers",
        type="",
        events=[],
        features=[],
        categories=[CategoryResult(
                layers=[LayerResult(
                        name="Layer_01",
                        serviceUrl="https://gibs.earthdata.nasa.gov/link/to/Layer_01",
                        serviceTypeId="Layer_01_ID",
                        parameters=[
                            {
                                "TILEMATRIXSET": "2km",
                                "FORMAT": "image/png"
                            }
                        ]
                    ),
                    LayerResult(
                        name="Layer_02",
                        serviceUrl="https://gibs.earthdata.nasa.gov/link/to/Layer_02",
                        serviceTypeId="Layer_02_ID",
                        parameters=[
                            {
                                "TILEMATRIXSET": "2km",
                                "FORMAT": "image/png"
                            }
                        ]
                    )
                ]
            )
        ]
    )
    
    result = tool.get_events(endpoint="layers", params={}, category="categoryId")

    assert result.status == SearchStatus.SUCCESS
    assert result.title == "EONET Web Service Layers"
    assert result.description == "List of web service layers in the EONET system"
    assert result.link == f"{EONET_BASE_URL}/layers"
    assert result.categories == [CategoryResult(
            layers=[LayerResult(
                    name="Layer_01",
                    serviceUrl="https://gibs.earthdata.nasa.gov/link/to/Layer_01",
                    serviceTypeId="Layer_01_ID",
                    parameters=[
                        {
                            "TILEMATRIXSET": "2km",
                            "FORMAT": "image/png"
                        }
                    ]
                ),
                LayerResult(
                    name="Layer_02",
                    serviceUrl="https://gibs.earthdata.nasa.gov/link/to/Layer_02",
                    serviceTypeId="Layer_02_ID",
                    parameters=[
                        {
                            "TILEMATRIXSET": "2km",
                            "FORMAT": "image/png"
                        }
                    ]
                )
            ]
        )
    ]
    mock_get_events.assert_called_once_with(endpoint="layers", params={}, category="categoryId")
    

def test_get_events_layers_returns_error_for_fake_category(mock_layers_endpoint: MagicMock, mock_get_events: MagicMock) -> None:
    """Test that get_events returns an error if a fake category is given (for layers endpoint)."""
    tool = _load_tool()
    
    mock_layers_endpoint.side_effect=EONETError("That category doesn't exist.")

    mock_get_events.return_value = GetEventsOutput(
        status=SearchStatus.ERROR,
        error_message=f"{ANY}",
        title=SearchStatus.ERROR,
        description="Failed EONET API request",
        link=f"{get_request_url()}",
        type="",
        events=[],
        features=[],
        categories=[],
    )
    
    with pytest.raises(EONETError) as e:
        results = tool.get_events(endpoint="layers", params={}, category="fakecategory")

    assert results.status == SearchStatus.ERROR
    assert results.error_message == f"{ANY}"
    assert results.title == SearchStatus.ERROR
    assert results.description == "Failed EONET API request"
    assert results.link == ANY
    assert results.type == ""
    assert results.events == []
    assert results.features == []
    assert results.categories == []
    mock_get_events.assert_called_once_with(endpoint="layers", params={}, category="fakecategory")
    assert "That category doesn't exist." in str(e.value)
