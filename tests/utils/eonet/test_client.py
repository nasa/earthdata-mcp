"""Tests for EONET API client."""

from unittest.mock import Mock, ANY

import requests

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

    def test_returns_multiple_events(self, monkeypatch):
        """Test that events returns multiple result successfully."""
        expected = {
            "title": "EONET Event",
            "description": "Natural event from EONET.",
            "link": "https://eonet.gsfc.nasa.gov/api/v3/events",
            "events": [{ "id": "exampleEvent1" }, { "id": "exampleEvent2" }]
        }
    
        mock_get = Mock(return_value=_make_response(json_data=expected))
        monkeypatch.setattr("util.eonet.client.requests.get", mock_get)
    
        params = {"limit": "2"}
    
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

    def test_events_return_failed(self, monkeypatch):
        """Test that events returns all results if an invalid request is made."""
        all_results = [{}] * 7204 # 7204 is the estimated number of events in EONET as of 2026-10-07
        expected = {
            "title": "EONET Event",
            "description": "Natural event from EONET.",
            "link": "https://eonet.gsfc.nasa.gov/api/v3/events",
            "events": all_results
        }
        
        mock_get = Mock(return_value=_make_response(json_data=expected))
        monkeypatch.setattr("util.eonet.client.requests.get", mock_get)
        
        params = {"limit": "-1"}
        
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

    def test_returns_multiple_events_geojson(self, monkeypatch):
        """Test that events can return multiple geojson results successfully."""
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
    
        params = {"limit": "2"}
        
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

    def test_events_geojson_return_failed(self, monkeypatch):
        """Test that events returns all results if an invalid geojson request is made."""
        all_results = [{}] * 8027 # 8027 is the estimated number of geojson events in EONET as of 2026-10-07
        expected = {
            "type": "FeatureCollection",
            "features": all_results
        }
        
        mock_get = Mock(return_value=_make_response(json_data=expected))
        monkeypatch.setattr("util.eonet.client.requests.get", mock_get)
        
        params = {"limit": "-1"}
        
        result = events(params, False)
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

    def test_returns_multiple_events_from_category(self, monkeypatch):
        """Test that categories returns multiple events from the specified category."""
        expected = {
            "title": "EONET Event",
            "description": "Natural event from EONET.",
            "link": "https://eonet.gsfc.nasa.gov/api/v3/categories/categoryId",
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
	        "link": f"https://eonet.gsfc.nasa.gov/api/v3/categories/categoryId",
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
        endpoint is called.
        """
        all_categories = [{}] * 13 # 13 is the number of categories in EONET as of 2026-10-07
        expected = {
	        "title": "EONET Event Categories",
	        "description": "List of all the available event categories in the EONET system",
	        "link": "https://eonet.gsfc.nasa.gov/api/v3/categories",
	        "categories": all_categories
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
        all_categories = [{}] * 7132 # 7132 is the estimated number of events for the Wildfires category as of 2026-10-07
        expected = {
	        "title": "EONET Events: Wildfires",
	        "description": "Wildland fires includes all nature of fire, in forest and plains, as well as those that spread to become urban and industrial fire events. Fires may be naturally caused or manmade.",
	        "link": "https://eonet.gsfc.nasa.gov/api/v3/categories/wildfires",
	        "events": all_categories
        }
        
        mock_get = Mock(return_value=_make_response(json_data=expected))
        monkeypatch.setattr("util.eonet.client.requests.get", mock_get)
        
        result_no_params = categories("wildfires", {})
        result_invalid_param = categories("wildfires", {"limit": "-1"})
        assert result_no_params == expected
        assert result_invalid_param == expected

    def test_returns_error_for_fake_category(self, monkeypatch):
        """Test that categories returns an error for a fake category."""
        expected = requests.exceptions.HTTPError()
        
        mock_get = Mock(return_value=_make_response(json_data=expected))
        mock_get.side_effect = requests.exceptions.HTTPError
        monkeypatch.setattr("util.eonet.client.requests.get", mock_get)
        
        result = categories("fakecategory", {})
        assert type(result) == type(expected)

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

    def test_returns_multiple_layers_from_category(self, monkeypatch):
        """Test that layers returns multiple layers from the specified category."""
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

    def test_returns_all_layers(self, monkeypatch):
        """Test that layers returns all layers when no category is given."""
        all_layers = [{}] * 201 # 201 is the estimated number of layers in EONET as of 2026-10-07
        expected = {
	        "title": "EONET Web Service Layers",
	        "description": "List of web service layers in the EONET system",
	        "link": "https://eonet.gsfc.nasa.gov/api/v3/layers",
	        "categories": [
                {
                    "layers": all_layers
                }
            ]
        }
        
        mock_get = Mock(return_value=_make_response(json_data=expected))
        monkeypatch.setattr("util.eonet.client.requests.get", mock_get)
        
        result = layers("categoryId")
        assert result == expected

    def test_layers_returns_error_for_fake_category(self, monkeypatch):
        """Test that layers returns an error if a fake category is given."""
        expected = requests.exceptions.HTTPError()
        
        mock_get = Mock(return_value=_make_response(json_data=expected))
        mock_get.side_effect = requests.exceptions.HTTPError
        monkeypatch.setattr("util.eonet.client.requests.get", mock_get)
        
        result = layers("fakecategory")
        assert type(result) == type(expected)
