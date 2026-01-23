"""Natural Language Geocoder Util Test"""

import json
from unittest.mock import Mock, patch

import pytest
from shapely.geometry import Polygon

from util.natural_language_geocoder import (
    convert_geometry_to_geojson,
    convert_text_to_geom,
    fix_geometry,
    lambda_safe_init,
)


class TestNaturalLanguageGeocoder:
    """Tests for natural_language_geocoder.py utility functions."""

    @patch("util.natural_language_geocoder.simplify_geometry")
    @patch("util.natural_language_geocoder.extract_geometry_from_text")
    @patch("util.natural_language_geocoder.BedrockNovaLLM")
    @patch("util.natural_language_geocoder.GeocodeIndexPlaceLookup")
    def test_convert_text_to_geom_success(
        self, mock_lookup, mock_llm_class, mock_extract, mock_simplify
    ):
        """Test successful conversion from text to geometry."""
        # Setup
        mock_llm_instance = mock_llm_class.return_value
        mock_lookup_instance = mock_lookup.return_value
        mock_geometry = Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])
        mock_extract.return_value = mock_geometry
        mock_simplify.return_value = "POLYGON((0 0,1 0,1 1,0 1,0 0))"

        # Execute
        result = convert_text_to_geom("San Francisco")

        # Assert
        assert result is not None
        assert result == "POLYGON((0 0,1 0,1 1,0 1,0 0))"
        mock_llm_class.assert_called_once()
        mock_lookup.assert_called_once()
        mock_extract.assert_called_once_with(
            mock_llm_instance, "San Francisco", mock_lookup_instance
        )
        mock_simplify.assert_called_once_with(geom=mock_geometry, max_points=1000)

    @patch("util.natural_language_geocoder.BedrockNovaLLM")
    def test_convert_text_to_geom_exception(self, mock_llm_class):
        """Test error handling in convert_text_to_geom."""
        mock_llm_class.side_effect = Exception("API Error")

        result = convert_text_to_geom("Invalid Location")

        assert result is None

    @patch("util.natural_language_geocoder.extract_geometry_from_text")
    @patch("util.natural_language_geocoder.BedrockNovaLLM")
    @patch("util.natural_language_geocoder.GeocodeIndexPlaceLookup")
    def test_convert_text_to_geom_extract_exception(
        self, mock_lookup, mock_llm_class, mock_extract
    ):
        """Test error handling when extract_geometry_from_text fails."""
        # Setup - actually use the mocked objects
        mock_llm_instance = mock_llm_class.return_value
        mock_lookup_instance = mock_lookup.return_value
        # Configure the extract function to raise an exception
        mock_extract.side_effect = Exception("Extraction failed")

        # Exercise
        result = convert_text_to_geom("San Francisco")

        # Verify
        assert result is None
        # Verify mocks were used
        mock_llm_class.assert_called_once()
        mock_lookup.assert_called_once()
        mock_extract.assert_called_once_with(
            mock_llm_instance, "San Francisco", mock_lookup_instance
        )

    @patch("util.natural_language_geocoder.simplify_geometry")
    @patch("util.natural_language_geocoder.extract_geometry_from_text")
    @patch("util.natural_language_geocoder.BedrockNovaLLM")
    @patch("util.natural_language_geocoder.GeocodeIndexPlaceLookup")
    def test_convert_text_to_geom_simplify_exception(
        self, mock_lookup, mock_llm_class, mock_extract, mock_simplify
    ):
        """Test error handling when simplify_geometry fails."""
        # Setup - actually use the mocked objects
        mock_llm_instance = mock_llm_class.return_value
        mock_lookup_instance = mock_lookup.return_value
        mock_geometry = Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])
        mock_extract.return_value = mock_geometry
        mock_simplify.side_effect = Exception("Simplification failed")

        result = convert_text_to_geom("San Francisco")

        assert result is None

        # Verify the mocks were called as expected
        mock_llm_class.assert_called_once()
        mock_lookup.assert_called_once()
        mock_extract.assert_called_once_with(
            mock_llm_instance, "San Francisco", mock_lookup_instance
        )
        mock_simplify.assert_called_once_with(geom=mock_geometry, max_points=1000)

    def test_fix_geometry_polygon(self):
        """Test fix_geometry with a polygon."""
        # Clockwise polygon (needs orientation fix)
        polygon = {
            "type": "Polygon",
            "coordinates": [[(0, 0), (0, 1), (1, 1), (1, 0), (0, 0)]],
        }

        result = fix_geometry(polygon)

        assert result["type"] == "Polygon"
        assert "coordinates" in result

    def test_fix_geometry_multipolygon(self):
        """Test fix_geometry with a multipolygon."""
        multipolygon = {
            "type": "MultiPolygon",
            "coordinates": [
                [[(0, 0), (0, 1), (1, 1), (1, 0), (0, 0)]],
                [[(2, 2), (2, 3), (3, 3), (3, 2), (2, 2)]],
            ],
        }

        result = fix_geometry(multipolygon)

        assert result["type"] == "MultiPolygon"
        assert len(result["coordinates"]) == 2

    def test_fix_geometry_point(self):
        """Test fix_geometry with a point (should return unchanged)."""
        point = {"type": "Point", "coordinates": [0, 0]}

        result = fix_geometry(point)

        assert result == point

    def test_fix_geometry_linestring(self):
        """Test fix_geometry with a linestring (should return unchanged)."""
        linestring = {"type": "LineString", "coordinates": [[0, 0], [1, 1]]}

        result = fix_geometry(linestring)

        assert result == linestring

    @patch("util.natural_language_geocoder.geometry_to_geojson")
    def test_convert_geometry_to_geojson_feature_collection(self, mock_geometry_to_geojson):
        """Test convert_geometry_to_geojson with a FeatureCollection."""
        mock_geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[(0, 0), (0, 1), (1, 1), (1, 0), (0, 0)]],
                    },
                    "properties": {},
                }
            ],
        }
        mock_geometry_to_geojson.return_value = json.dumps(mock_geojson)

        result = convert_geometry_to_geojson("mock_geometry")

        assert result["type"] == "FeatureCollection"
        assert len(result["features"]) == 1

    @patch("util.natural_language_geocoder.geometry_to_geojson")
    def test_convert_geometry_to_geojson_feature(self, mock_geometry_to_geojson):
        """Test convert_geometry_to_geojson with a Feature."""
        mock_geojson = {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[(0, 0), (0, 1), (1, 1), (1, 0), (0, 0)]],
            },
            "properties": {},
        }
        mock_geometry_to_geojson.return_value = json.dumps(mock_geojson)

        result = convert_geometry_to_geojson("mock_geometry")

        assert result["type"] == "Feature"
        assert result["geometry"]["type"] == "Polygon"

    @patch("util.natural_language_geocoder.geometry_to_geojson")
    def test_convert_geometry_to_geojson_geometry_only(self, mock_geometry_to_geojson):
        """Test convert_geometry_to_geojson with geometry only."""
        mock_geojson = {
            "type": "Polygon",
            "coordinates": [[(0, 0), (0, 1), (1, 1), (1, 0), (0, 0)]],
        }
        mock_geometry_to_geojson.return_value = json.dumps(mock_geojson)

        result = convert_geometry_to_geojson("mock_geometry")

        assert result["type"] == "Polygon"

    @patch("util.natural_language_geocoder.geometry_to_geojson")
    def test_convert_geometry_to_geojson_attribute_error(self, mock_geometry_to_geojson):
        """Test convert_geometry_to_geojson with AttributeError."""
        mock_geometry_to_geojson.side_effect = AttributeError("Invalid geometry")

        with pytest.raises(ValueError) as excinfo:
            convert_geometry_to_geojson("invalid_geometry")

        assert "Failed to convert geometry to GeoJSON" in str(excinfo.value)

    @patch("util.natural_language_geocoder.geometry_to_geojson")
    def test_convert_geometry_to_geojson_json_decode_error(self, mock_geometry_to_geojson):
        """Test convert_geometry_to_geojson with JSONDecodeError."""
        mock_geometry_to_geojson.return_value = "invalid json"

        with pytest.raises(ValueError) as excinfo:
            convert_geometry_to_geojson("mock_geometry")

        assert "Failed to convert geometry to GeoJSON" in str(excinfo.value)

    @patch("util.natural_language_geocoder.geometry_to_geojson")
    def test_convert_geometry_to_geojson_value_error(self, mock_geometry_to_geojson):
        """Test convert_geometry_to_geojson with ValueError."""
        mock_geometry_to_geojson.side_effect = ValueError("Conversion failed")

        with pytest.raises(ValueError) as excinfo:
            convert_geometry_to_geojson("invalid_geometry")

        assert "Failed to convert geometry to GeoJSON" in str(excinfo.value)


@patch("util.natural_language_geocoder._original_init")
def test_lambda_safe_init_default_cache_dir(mock_original_init):
    """Test lambda_safe_init with ./temp cache_dir (should change to /tmp)."""

    mock_self = Mock()
    mock_original_init.return_value = None

    # Test with "./temp" - should be changed to "/tmp"
    lambda_safe_init(mock_self, cache_dir="./temp")

    # Verify _original_init was called with /tmp
    mock_original_init.assert_called_once_with(mock_self, cache_dir="/tmp")
