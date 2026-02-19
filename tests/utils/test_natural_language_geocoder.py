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

    def test_orients_polygon_exterior_to_ccw(self):
        """Test that polygons are oriented counter-clockwise (exterior ring counter-clockwise)."""
        # Create a CW polygon (CMR requires CCW)
        cw_polygon = Polygon([(0, 0), (0, 1), (1, 1), (1, 0), (0, 0)])

        result = _normalize_geometry_to_wkt(cw_polygon)

        assert result is not None
        from shapely import wkt

        result_geom = wkt.loads(result)
        assert LinearRing(result_geom.exterior.coords).is_ccw

    def test_preserves_ccw_polygon_orientation(self):
        """Test that counter-clockwise polygons remain counter-clockwise."""
        # Create a CCW polygon
        ccw_polygon = Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])

        result = _normalize_geometry_to_wkt(ccw_polygon)

        assert result is not None
        from shapely import wkt

        result_geom = wkt.loads(result)
        assert LinearRing(result_geom.exterior.coords).is_ccw

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

    def test_repairs_invalid_geometry_with_make_valid(self):
        """Test that invalid geometries are repaired using make_valid()."""
        # Create a self-intersecting polygon (bow-tie shape)
        invalid_polygon = Polygon([(0, 0), (2, 2), (2, 0), (0, 2), (0, 0)])

        # Should not raise, should repair with make_valid()
        result = _normalize_geometry_to_wkt(invalid_polygon)

        assert result is not None
        # make_valid() on a bow-tie produces a MultiPolygon (two triangles)
        assert result.startswith("POLYGON") or result.startswith("MULTIPOLYGON")

    def test_raises_validation_error_for_unrepairable_geometry(self):
        """Test that geometries that can't be repaired raise ValueError."""
        # Mock a geometry that is_valid returns False even after make_valid()
        mock_geom = MagicMock()
        mock_geom.geom_type = "Polygon"
        mock_geom.is_empty = False
        mock_geom.is_valid = False

        with patch("util.natural_language_geocoder.make_valid") as mock_make_valid:
            mock_make_valid.return_value.is_empty = False
            mock_make_valid.return_value.is_valid = False
            mock_make_valid.return_value.geom_type = "Polygon"

            with pytest.raises(ValueError, match="could not be repaired"):
                _normalize_geometry_to_wkt(mock_geom)

    def test_raises_validation_error_when_make_valid_raises_exception(self):
        """Test that exceptions during make_valid() are caught."""
        mock_geom = MagicMock()
        mock_geom.geom_type = "Polygon"
        mock_geom.is_empty = False
        mock_geom.is_valid = False

        with patch(
            "util.natural_language_geocoder.make_valid", side_effect=Exception("make_valid failed")
        ):
            with pytest.raises(ValueError, match="Invalid geometry"):
                _normalize_geometry_to_wkt(mock_geom)

    def test_valid_geometry_skips_make_valid(self):
        """Test that make_valid() is never called when geometry is already valid."""
        valid_polygon = Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])
        assert valid_polygon.is_valid

        with patch("util.natural_language_geocoder.make_valid") as mock_make_valid:
            _normalize_geometry_to_wkt(valid_polygon)

        mock_make_valid.assert_not_called()

    def test_repair_emits_warning_log(self, caplog):
        """Test that repairing an invalid geometry emits a WARNING log."""
        invalid_polygon = Polygon([(0, 0), (2, 2), (2, 0), (0, 2), (0, 0)])
        assert not invalid_polygon.is_valid

        with caplog.at_level("WARNING"):
            _normalize_geometry_to_wkt(invalid_polygon)

        assert any("make_valid" in record.message for record in caplog.records)

    def test_raises_when_make_valid_returns_empty_geometry(self):
        """Test that a ValueError is raised when make_valid() produces an empty geometry."""
        mock_geom = MagicMock()
        mock_geom.geom_type = "Polygon"
        mock_geom.is_empty = False
        mock_geom.is_valid = False

        with patch("util.natural_language_geocoder.make_valid") as mock_make_valid:
            mock_make_valid.return_value.is_empty = True

            with pytest.raises(ValueError, match="empty after make_valid"):
                _normalize_geometry_to_wkt(mock_geom)

    def test_invalid_polygon_repaired_and_exterior_is_ccw(self):
        """Test that an invalid self-intersecting polygon is repaired and reoriented counter-clockwise."""
        # Bow-tie shape — self-intersecting, invalid
        invalid_polygon = Polygon([(0, 0), (2, 2), (2, 0), (0, 2), (0, 0)])
        assert not invalid_polygon.is_valid

        result = _normalize_geometry_to_wkt(invalid_polygon)

        assert result is not None
        from shapely import wkt as shapely_wkt

        repaired = shapely_wkt.loads(result)
        # make_valid() on a bow-tie typically produces a MultiPolygon
        if repaired.geom_type == "MultiPolygon":
            for part in repaired.geoms:
                assert LinearRing(
                    part.exterior.coords
                ).is_ccw, f"Exterior ring of repaired part is not CCW: {part}"
        else:
            assert LinearRing(repaired.exterior.coords).is_ccw

    def test_orients_cw_multipolygon_exterior_to_ccw(self):
        """Test that a MultiPolygon with clockwise exterior rings is reoriented to counter-clockwise."""
        # Explicitly CW polygons
        cw_poly1 = Polygon([(0, 0), (0, 1), (1, 1), (1, 0), (0, 0)])
        cw_poly2 = Polygon([(2, 0), (2, 1), (3, 1), (3, 0), (2, 0)])
        assert not LinearRing(cw_poly1.exterior.coords).is_ccw
        assert not LinearRing(cw_poly2.exterior.coords).is_ccw

        result = _normalize_geometry_to_wkt(MultiPolygon([cw_poly1, cw_poly2]))

        assert result is not None
        from shapely import wkt as shapely_wkt

        oriented = shapely_wkt.loads(result)
        assert oriented.geom_type == "MULTIPOLYGON" or oriented.geom_type == "MultiPolygon"
        for part in oriented.geoms:
            assert LinearRing(
                part.exterior.coords
            ).is_ccw, f"Exterior ring of MultiPolygon part is not CCW: {part}"

    def test_preserves_ccw_multipolygon_orientation(self):
        """Test that a MultiPolygon already counter-clockwise stays counter-clockwise after normalization."""
        ccw_poly1 = Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])
        ccw_poly2 = Polygon([(2, 0), (3, 0), (3, 1), (2, 1), (2, 0)])

        result = _normalize_geometry_to_wkt(MultiPolygon([ccw_poly1, ccw_poly2]))

        assert result is not None
        from shapely import wkt as shapely_wkt

        oriented = shapely_wkt.loads(result)
        for part in oriented.geoms:
            assert LinearRing(part.exterior.coords).is_ccw

    def test_polygon_with_hole_exterior_ccw_and_hole_cw(self):
        """Test that a Polygon with a hole has counter-clockwise exterior and clockwise interior ring."""
        exterior = [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]
        # Interior ring (hole) — deliberately CCW so orient_polygons must flip it to CW
        hole = [(2, 2), (4, 2), (4, 4), (2, 4), (2, 2)]
        polygon_with_hole = Polygon(exterior, [hole])

        result = _normalize_geometry_to_wkt(polygon_with_hole)

        assert result is not None
        from shapely import wkt as shapely_wkt

        oriented = shapely_wkt.loads(result)
        assert LinearRing(oriented.exterior.coords).is_ccw, "Exterior ring should be CCW"
        for interior in oriented.interiors:
            assert not LinearRing(interior.coords).is_ccw, "Interior ring (hole) should be CW"

    def test_polygon_with_cw_exterior_and_ccw_hole_both_reoriented(self):
        """Test that a Polygon with a clockwise exterior and counter-clockwise hole has both rings reoriented."""
        # CW exterior — needs flipping to CCW
        cw_exterior = [(0, 0), (0, 10), (10, 10), (10, 0), (0, 0)]
        # CCW hole — needs flipping to CW
        ccw_hole = [(2, 2), (4, 2), (4, 4), (2, 4), (2, 2)]
        assert not LinearRing(cw_exterior).is_ccw
        assert LinearRing(ccw_hole).is_ccw
        polygon_with_hole = Polygon(cw_exterior, [ccw_hole])

        result = _normalize_geometry_to_wkt(polygon_with_hole)

        assert result is not None
        from shapely import wkt as shapely_wkt

        oriented = shapely_wkt.loads(result)
        assert LinearRing(oriented.exterior.coords).is_ccw, "Exterior ring should be CCW"
        for interior in oriented.interiors:
            assert not LinearRing(interior.coords).is_ccw, "Interior ring (hole) should be CW"

    def test_multipolygon_with_holes_exterior_ccw_and_holes_cw(self):
        """Test that each part of a MultiPolygon with holes has counter-clockwise exterior and clockwise holes."""
        exterior1 = [(0, 0), (0, 10), (10, 10), (10, 0), (0, 0)]  # CW exterior
        hole1 = [(2, 2), (4, 2), (4, 4), (2, 4), (2, 2)]  # CCW hole
        exterior2 = [(20, 0), (20, 10), (30, 10), (30, 0), (20, 0)]  # CW exterior
        hole2 = [(22, 2), (24, 2), (24, 4), (22, 4), (22, 2)]  # CCW hole
        mp = MultiPolygon(
            [
                Polygon(exterior1, [hole1]),
                Polygon(exterior2, [hole2]),
            ]
        )

        result = _normalize_geometry_to_wkt(mp)

        assert result is not None
        from shapely import wkt as shapely_wkt

        oriented = shapely_wkt.loads(result)
        for part in oriented.geoms:
            assert LinearRing(
                part.exterior.coords
            ).is_ccw, f"Exterior ring of part is not CCW: {part}"
            for interior in part.interiors:
                assert not LinearRing(
                    interior.coords
                ).is_ccw, f"Interior ring (hole) of part is not CW: {interior}"

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
