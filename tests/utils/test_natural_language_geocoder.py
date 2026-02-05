"""Tests for natural language geocoder WKT conversion."""

from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from shapely.geometry import LinearRing, LineString, MultiPolygon, Point, Polygon

from util.natural_language_geocoder import _normalize_geometry_to_wkt, convert_text_to_geom


class TestNormalizeGeometryToWkt:
    """Tests for _normalize_geometry_to_wkt function."""

    def test_converts_simple_polygon_to_wkt(self):
        """Test basic Shapely polygon to WKT conversion."""
        polygon = Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])

        result = _normalize_geometry_to_wkt(polygon)

        assert result is not None
        assert result.startswith("POLYGON")
        assert "0 0" in result

    def test_converts_point_to_wkt(self):
        """Test Point geometry conversion."""
        point = Point(10.5, 20.3)

        result = _normalize_geometry_to_wkt(point)

        assert result is not None
        assert result.startswith("POINT")
        assert "10.5" in result
        assert "20.3" in result

    def test_returns_none_for_none_input(self):
        """Test that None input returns None."""
        result = _normalize_geometry_to_wkt(None)

        assert result is None

    def test_raises_validation_error_for_non_shapely_object(self):
        """Test that non-Shapely objects raise ValueError."""
        with pytest.raises(ValueError, match="Expected Shapely geometry object"):
            _normalize_geometry_to_wkt("not a geometry")

    def test_repairs_invalid_geometry_with_buffer(self):
        """Test that invalid geometries are repaired using buffer(0)."""
        # Create a self-intersecting polygon (bow-tie shape)
        invalid_polygon = Polygon([(0, 0), (2, 2), (2, 0), (0, 2), (0, 0)])

        # Should not raise, should repair with buffer(0)
        result = _normalize_geometry_to_wkt(invalid_polygon)

        assert result is not None
        assert result.startswith("POLYGON")

    def test_raises_validation_error_for_unrepairable_geometry(self):
        """Test that geometries that can't be repaired raise ValueError."""
        # Mock a geometry that is_valid returns False even after buffer
        mock_geom = MagicMock()
        mock_geom.geom_type = "Polygon"
        mock_geom.is_empty = False
        mock_geom.is_valid = False
        mock_geom.buffer.return_value.is_empty = False
        mock_geom.buffer.return_value.is_valid = False

        with pytest.raises(ValueError, match="could not be repaired"):
            _normalize_geometry_to_wkt(mock_geom)

    def test_raises_validation_error_when_buffer_raises_exception(self):
        """Test that exceptions during buffer operation are caught."""
        mock_geom = MagicMock()
        mock_geom.geom_type = "Polygon"
        mock_geom.is_empty = False
        mock_geom.is_valid = False
        mock_geom.buffer.side_effect = Exception("Buffer failed")

        with pytest.raises(ValueError, match="Invalid geometry"):
            _normalize_geometry_to_wkt(mock_geom)


class TestConvertTextToGeom:
    """Tests for convert_text_to_geom function."""

    @patch("util.natural_language_geocoder.extract_geometry_from_text")
    @patch("util.natural_language_geocoder.simplify_geometry")
    @patch("util.natural_language_geocoder.BedrockNovaLLM")
    @patch("util.natural_language_geocoder.GeocodeIndexPlaceLookup")
    def test_successful_geocoding_returns_wkt(
        self, mock_lookup, mock_llm, mock_simplify, mock_extract
    ):
        """Test successful geocoding flow returns WKT string."""
        # Setup mocks
        polygon = Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])
        mock_extract.return_value = polygon
        mock_simplify.return_value = polygon

        result = convert_text_to_geom("Pacific Ocean")

        assert result is not None
        assert isinstance(result, str)
        assert result.startswith("POLYGON")
        mock_extract.assert_called_once()
        mock_simplify.assert_called_once()

    @patch("util.natural_language_geocoder.extract_geometry_from_text")
    @patch("util.natural_language_geocoder.simplify_geometry")
    @patch("util.natural_language_geocoder.BedrockNovaLLM")
    @patch("util.natural_language_geocoder.GeocodeIndexPlaceLookup")
    def test_returns_none_on_validation_error(
        self, mock_lookup, mock_llm, mock_simplify, mock_extract
    ):
        """Test that ValidationError from normalization results in None return."""
        polygon = Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])
        mock_extract.return_value = polygon

        # Mock simplify to return something that will fail validation
        mock_geom = MagicMock()
        mock_geom.geom_type = "Polygon"
        mock_geom.is_empty = False
        mock_geom.is_valid = False
        mock_geom.buffer.side_effect = Exception("Can't repair")
        mock_simplify.return_value = mock_geom

        result = convert_text_to_geom("Test location")

        assert result is None

    @patch("util.natural_language_geocoder.extract_geometry_from_text")
    @patch("util.natural_language_geocoder.BedrockNovaLLM")
    @patch("util.natural_language_geocoder.GeocodeIndexPlaceLookup")
    def test_returns_none_on_unexpected_exception(self, mock_lookup, mock_llm, mock_extract):
        """Test that unexpected exceptions are caught and None is returned."""
        mock_extract.side_effect = RuntimeError("Unexpected error")

        result = convert_text_to_geom("Test location")

        assert result is None

    @patch("util.natural_language_geocoder.extract_geometry_from_text")
    @patch("util.natural_language_geocoder.simplify_geometry")
    @patch("util.natural_language_geocoder.BedrockNovaLLM")
    @patch("util.natural_language_geocoder.GeocodeIndexPlaceLookup")
    def test_logs_geometry_details(
        self, mock_lookup, mock_llm, mock_simplify, mock_extract, caplog
    ):
        """Test that geometry details are logged for debugging."""
        polygon = Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])
        mock_extract.return_value = polygon
        mock_simplify.return_value = polygon

        with caplog.at_level("DEBUG"):
            convert_text_to_geom("Test location")

        # Check that geometry info was logged
        assert any("Extracted geometry" in record.message for record in caplog.records)

    @patch("util.natural_language_geocoder.extract_geometry_from_text")
    @patch("util.natural_language_geocoder.simplify_geometry")
    @patch("util.natural_language_geocoder.BedrockNovaLLM")
    @patch("util.natural_language_geocoder.GeocodeIndexPlaceLookup")
    def test_logs_point_geometry_details(
        self, mock_lookup, mock_llm, mock_simplify, mock_extract, caplog
    ):
        """Test that Point geometry details are logged correctly."""
        point = Point(10.5, 20.3)
        mock_extract.return_value = point
        mock_simplify.return_value = point

        with caplog.at_level("DEBUG"):
            convert_text_to_geom("Test location")

        # Check that geometry info with num_coords=1 was logged
        assert any("Extracted geometry" in record.message for record in caplog.records)

    @patch("util.natural_language_geocoder.extract_geometry_from_text")
    @patch("util.natural_language_geocoder.simplify_geometry")
    @patch("util.natural_language_geocoder.BedrockNovaLLM")
    @patch("util.natural_language_geocoder.GeocodeIndexPlaceLookup")
    def test_handles_geometry_logging_exception(
        self, mock_lookup, mock_llm, mock_simplify, mock_extract, caplog
    ):
        """Test that exceptions during geometry logging don't break the flow."""
        # Mock geometry that raises exception when accessing geom_type
        mock_geom = MagicMock()
        type(mock_geom).geom_type = PropertyMock(side_effect=Exception("boom"))

        mock_extract.return_value = mock_geom
        mock_simplify.return_value = Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])

        # Should not raise, should continue to simplification and conversion
        result = convert_text_to_geom("Test location")

        assert result is not None

    @patch("util.natural_language_geocoder.extract_geometry_from_text")
    @patch("util.natural_language_geocoder.simplify_geometry")
    @patch("util.natural_language_geocoder.BedrockNovaLLM")
    @patch("util.natural_language_geocoder.GeocodeIndexPlaceLookup")
    def test_logs_linestring_geometry_details(
        self, mock_lookup, mock_llm, mock_simplify, mock_extract, caplog
    ):
        """Test that LineString geometry details are logged correctly."""
        linestring = LineString([(0, 0), (1, 1), (2, 2)])
        mock_extract.return_value = linestring
        mock_simplify.return_value = linestring

        with caplog.at_level("DEBUG"):
            convert_text_to_geom("Test location")

        # Check that geometry info with num_coords was logged
        assert any("Extracted geometry" in record.message for record in caplog.records)

    @patch("util.natural_language_geocoder.extract_geometry_from_text")
    @patch("util.natural_language_geocoder.simplify_geometry")
    @patch("util.natural_language_geocoder.BedrockNovaLLM")
    @patch("util.natural_language_geocoder.GeocodeIndexPlaceLookup")
    def test_logs_linearring_geometry_details(
        self, mock_lookup, mock_llm, mock_simplify, mock_extract, caplog
    ):
        """Test that LinearRing geometry details are logged correctly."""
        linearring = LinearRing([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])
        mock_extract.return_value = linearring
        mock_simplify.return_value = linearring

        with caplog.at_level("DEBUG"):
            convert_text_to_geom("Test location")

        # Check that geometry info with num_coords was logged
        assert any("Extracted geometry" in record.message for record in caplog.records)

    @patch("util.natural_language_geocoder.extract_geometry_from_text")
    @patch("util.natural_language_geocoder.simplify_geometry")
    @patch("util.natural_language_geocoder.BedrockNovaLLM")
    @patch("util.natural_language_geocoder.GeocodeIndexPlaceLookup")
    def test_logs_multipolygon_geometry_details(
        self, mock_lookup, mock_llm, mock_simplify, mock_extract, caplog
    ):
        """Test that MultiPolygon geometry details are logged correctly."""
        poly1 = Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])
        poly2 = Polygon([(2, 2), (3, 2), (3, 3), (2, 3), (2, 2)])
        multipolygon = MultiPolygon([poly1, poly2])

        mock_extract.return_value = multipolygon
        mock_simplify.return_value = multipolygon

        with caplog.at_level("DEBUG"):
            convert_text_to_geom("Test location")

        # Check that geometry info with num_parts was logged
        assert any("Extracted geometry" in record.message for record in caplog.records)
