"""Tests for EONET API client."""

from unittest.mock import Mock

from util.eonet.client import (
    EONET_BASE_URL,
    events,
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
            "link": f"{EONET_BASE_URL}/events",
            "events": [{"id": "exampleEvent"}],
        }

        mock_get = Mock(return_value=_make_response(json_data=expected))
        monkeypatch.setattr("util.eonet.client.requests.get", mock_get)

        params = {"limit": "1"}

        result = events(params, False)
        assert result == expected

    def test_returns_multiple_events(self, monkeypatch):
        """Test that events returns multiple results successfully."""
        expected = {
            "title": "EONET Event",
            "description": "Natural events from EONET.",
            "link": f"{EONET_BASE_URL}/events",
            "events": [{"id": "exampleEvent1"}, {"id": "exampleEvent2"}],
        }

        mock_get = Mock(return_value=_make_response(json_data=expected))
        monkeypatch.setattr("util.eonet.client.requests.get", mock_get)

        params = {"limit": "2"}

        result = events(params, False)
        assert result == expected

    def test_returns_no_events(self, monkeypatch):
        """Test that events can return no results successfully."""
        expected = {
            "title": "EONET Events",
            "description": "Natural events from EONET.",
            "link": f"{EONET_BASE_URL}/events",
            "events": [],
        }

        mock_get = Mock(return_value=_make_response(json_data=expected))
        monkeypatch.setattr("util.eonet.client.requests.get", mock_get)

        params = {"limit": "1"}

        result = events(params, False)
        assert result == expected

    def test_events_return_failed(self, monkeypatch):
        """Test that events returns all results if an invalid request is made."""
        expected = {
            "title": "EONET Event",
            "description": "Natural events from EONET.",
            "link": f"{EONET_BASE_URL}/events",
            "events": [{"id": "exampleEvent1"}, {"id": "exampleEvent2"}],
        }

        mock_get = Mock(return_value=_make_response(json_data=expected))
        monkeypatch.setattr("util.eonet.client.requests.get", mock_get)

        params = {"limit": "-1"}

        result = events(params, False)
        assert result == expected

    def test_returns_event_geojson(self, monkeypatch):
        """Test that events can return a geojson result successfully."""
        expected = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [0.0, 0.0]},
                    "properties": {"name": "A Cool Place", "location": "Anytown, USA"},
                }
            ],
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

        mock_get = Mock(return_value=_make_response(json_data=expected))
        monkeypatch.setattr("util.eonet.client.requests.get", mock_get)

        params = {"limit": "2"}

        result = events(params, True)
        assert result == expected

    def test_returns_no_events_geojson(self, monkeypatch):
        """Test that events can return no geojson results successfully."""
        expected = {"type": "FeatureCollection", "features": []}

        mock_get = Mock(return_value=_make_response(json_data=expected))
        monkeypatch.setattr("util.eonet.client.requests.get", mock_get)

        params = {"limit": "1"}

        result = events(params, True)
        assert result == expected

    def test_events_geojson_return_failed(self, monkeypatch):
        """Test that events returns all results if an invalid geojson request is made."""
        expected = {
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
            "events": [{"id": "exampleEvent1"}, {"id": "exampleEvent2"}],
        }

        mock_get = Mock(return_value=_make_response(json_data=expected))
        monkeypatch.setattr("util.eonet.client.requests.get", mock_get)

        params = {"category": "fakecategory"}

        result = events(params, False)
        assert result == expected
