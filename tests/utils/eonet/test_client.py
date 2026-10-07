"""Tests for EONET API client."""

from unittest.mock import Mock, ANY

import re

from util.eonet.client import (
    events,
    categories,
    layers,
)

def _make_response(*, json_data=None):
    """Build a mock requests.Response with configurable attributes."""
    response = Mock()
    response.json.return_value = json_data or {}
    response.raise_for_status.return_value = None
    return response

class TestEvents:
    """Test the events function."""

    def test_returns_event(self, monkeypatch):
        """Test that events returns a result successfully."""
        expected = {
            "title": "EONET Event",
            "description": "Natural event from EONET.",
            "link": "https://eonet.gsfc.nasa.gov/api/v3/events",
            "events": [{ "id": "exampleEvent" }]
        }

        mock_get = Mock(return_value=_make_response(json_data=expected))
        monkeypatch.setattr("util.eonet.client.requests.get", mock_get)

        params = {"limit": "1"}

        result = events(params, False)
        assert result == expected

    def test_returns_no_events(self, monkeypatch):
        """Test that events can return no results successfully."""
        expected = {}
    
        mock_get = Mock(return_value=_make_response(json_data=expected))
        monkeypatch.setattr("util.eonet.client.requests.get", mock_get)
    
        params = {"limit": "1"}
    
        result = events(params, False)
        assert result == expected

    def test_returns_event_geojson(self, monkeypatch):
        """Test that events can return a geojson result successfully."""
        expected = {
            "type": "Feature",
            "geometry": {
              "type": "Point",
              "coordinates": [0.0, 0.0] 
            },
            "properties": {
              "name": "A Cool Place",
              "location": "Anytown, USA"
            }
        }
    
        mock_get = Mock(return_value=_make_response(json_data=expected))
        monkeypatch.setattr("util.eonet.client.requests.get", mock_get)

        params = {"limit": "1"}
    
        result = events(params, True)
        assert result == expected

    def test_returns_no_events_geojson(self, monkeypatch):
        """Test that events can return no geojson results successfully."""
        expected = {}
        
        mock_get = Mock(return_value=_make_response(json_data=expected))
        monkeypatch.setattr("util.eonet.client.requests.get", mock_get)
    
        params = {"limit": "1"}
        
        result = events(params, True)
        assert result == expected

    def test_returns_event_from_category(self, monkeypatch):
        """Test that categories returns events from the specified category."""
        expected = {
            "title": "EONET Event",
            "description": "Natural event from EONET.",
            "link": "https://eonet.gsfc.nasa.gov/api/v3/categories/categoryId",
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

    def test_returns_no_events_from_category(self, monkeypatch):
        """Test that categories returns no events for a category without events."""
        expected = {
	        "title": ANY,
	        "description": ANY,
	        "link": f"https://eonet.gsfc.nasa.gov/api/v3/categories/categoryId",
	        "events": []
        }
        
        mock_get = Mock(return_value=_make_response(json_data=expected))
        monkeypatch.setattr("util.eonet.client.requests.get", mock_get)
    
        params = {"limit": "1"}
    
        result = categories("categoryId", params)
        assert result == expected

    def test_returns_layer_from_category(self, monkeypatch):
        """Test that layers returns layers from the specified category."""
        expected = {
            "title": "EONET Layers",
            "description": "Layers for the specified category.",
            "link": "https://eonet.gsfc.nasa.gov/api/v3/layers/categoryId",
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

    def test_returns_no_layers_from_category(self, monkeypatch):
        """Test that layers returns no layers for a category without layers."""
        expected = {
            "title": ANY,
            "description": ANY,
            "link": "https://eonet.gsfc.nasa.gov/api/v3/layers/categoryId",
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
