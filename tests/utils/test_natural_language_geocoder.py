"""Tests for util.natural_language_geocoder."""

from unittest.mock import MagicMock, patch

import pytest
from shapely.geometry import MultiPolygon, Point, Polygon

from util.natural_language_geocoder import _normalize_geometry_to_wkt, convert_text_to_geom


def test_normalize_geometry_to_wkt_none():
    """Test function."""
    assert _normalize_geometry_to_wkt(None) is None


def test_normalize_geometry_to_wkt_invalid_type():
    """Test function."""
    with pytest.raises(ValueError, match="Expected Shapely geometry object"):
        _normalize_geometry_to_wkt("not_geometry")


def test_normalize_geometry_to_wkt_point():
    """Test function."""
    p = Point(1, 2)
    assert _normalize_geometry_to_wkt(p) == "POINT (1 2)"


def test_normalize_geometry_to_wkt_polygon():
    """Test function."""
    p = Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])
    assert _normalize_geometry_to_wkt(p).startswith("POLYGON")


def test_normalize_geometry_to_wkt_invalid_geometry():
    """Test function."""
    # A bow-tie polygon is invalid
    p = Polygon([(0, 0), (2, 2), (0, 2), (2, 0), (0, 0)])
    assert not p.is_valid
    wkt = _normalize_geometry_to_wkt(p)
    assert wkt is not None
    assert "MULTIPOLYGON" in wkt or "POLYGON" in wkt


def test_normalize_geometry_to_wkt_repair_fails():
    """Test function."""
    p = MagicMock()
    p.geom_type = "Polygon"
    p.is_valid = False

    with (
        patch("util.natural_language_geocoder.make_valid", side_effect=Exception("repair failed")),
        pytest.raises(ValueError, match="Invalid geometry: repair failed"),
    ):
        _normalize_geometry_to_wkt(p)


def test_normalize_geometry_to_wkt_repair_empty():
    """Test function."""
    p = MagicMock()
    p.geom_type = "Polygon"
    p.is_valid = False

    repaired = MagicMock()
    repaired.is_empty = True

    with (
        patch("util.natural_language_geocoder.make_valid", return_value=repaired),
        pytest.raises(ValueError, match="Geometry is empty after make_valid"),
    ):
        _normalize_geometry_to_wkt(p)


def test_normalize_geometry_to_wkt_repair_still_invalid():
    """Test function."""
    p = MagicMock()
    p.geom_type = "Polygon"
    p.is_valid = False

    repaired = MagicMock()
    repaired.is_empty = False
    repaired.is_valid = False

    with (
        patch("util.natural_language_geocoder.make_valid", return_value=repaired),
        pytest.raises(ValueError, match="Geometry is invalid and could not be repaired"),
    ):
        _normalize_geometry_to_wkt(p)


def test_convert_text_to_geom_success():
    """Test function."""
    p = Point(1, 2)
    with (
        patch("util.natural_language_geocoder.BedrockNovaLLM"),
        patch("util.natural_language_geocoder.extract_geometry_from_text", return_value=p),
        patch("util.natural_language_geocoder.GeocodeIndexPlaceLookup"),
        patch("util.natural_language_geocoder.simplify_geometry", return_value=p),
    ):
        res = convert_text_to_geom("Test place")
        assert res == "POINT (1 2)"


def test_convert_text_to_geom_exception():
    """Test function."""
    with patch(
        "util.natural_language_geocoder.BedrockNovaLLM", side_effect=Exception("LLM failed")
    ):
        res = convert_text_to_geom("Test place")
        assert res is None


def test_convert_text_to_geom_logging_line_string():
    """Test function."""
    from shapely.geometry import LineString

    ls = LineString([(0, 0), (1, 1)])
    with (
        patch("util.natural_language_geocoder.BedrockNovaLLM"),
        patch("util.natural_language_geocoder.extract_geometry_from_text", return_value=ls),
        patch("util.natural_language_geocoder.GeocodeIndexPlaceLookup"),
        patch("util.natural_language_geocoder.simplify_geometry", return_value=ls),
    ):
        res = convert_text_to_geom("Test place")
        assert res == "LINESTRING (0 0, 1 1)"


def test_convert_text_to_geom_logging_multi():
    """Test function."""
    from shapely.geometry import MultiPoint

    mp = MultiPoint([(0, 0), (1, 1)])
    with (
        patch("util.natural_language_geocoder.BedrockNovaLLM"),
        patch("util.natural_language_geocoder.extract_geometry_from_text", return_value=mp),
        patch("util.natural_language_geocoder.GeocodeIndexPlaceLookup"),
        patch("util.natural_language_geocoder.simplify_geometry", return_value=mp),
    ):
        res = convert_text_to_geom("Test place")
        assert res == "MULTIPOINT ((0 0), (1 1))"


def test_convert_text_to_geom_logging_exception():
    """Test function."""
    p = Point(1, 2)
    # mock geom_type to throw to hit the exception block in logging
    p_mock = MagicMock()
    type(p_mock).geom_type = property(lambda _: _throw())

    def _throw():
        raise ValueError("Log failed")

    with (
        patch("util.natural_language_geocoder.BedrockNovaLLM"),
        patch("util.natural_language_geocoder.extract_geometry_from_text", return_value=p_mock),
        patch("util.natural_language_geocoder.GeocodeIndexPlaceLookup"),
        patch("util.natural_language_geocoder.simplify_geometry", return_value=p),
    ):
        res = convert_text_to_geom("Test place")
        assert res == "POINT (1 2)"


def test_convert_text_to_geom_logging_linear_ring():
    """Test function."""
    from shapely.geometry.polygon import LinearRing

    lr = LinearRing([(0, 0), (1, 1), (1, 0), (0, 0)])
    with (
        patch("util.natural_language_geocoder.BedrockNovaLLM"),
        patch("util.natural_language_geocoder.extract_geometry_from_text", return_value=lr),
        patch("util.natural_language_geocoder.GeocodeIndexPlaceLookup"),
        patch("util.natural_language_geocoder.simplify_geometry", return_value=lr),
    ):
        res = convert_text_to_geom("Test place")
        assert res == "LINEARRING (0 0, 1 1, 1 0, 0 0)"


def test_convert_text_to_geom_logging_polygon():
    """Test logging properties of a Polygon."""
    with (
        patch("util.natural_language_geocoder.extract_geometry_from_text") as mock_extract,
        patch("util.natural_language_geocoder.GeocodeIndexPlaceLookup"),
        patch("util.natural_language_geocoder.simplify_geometry") as mock_simplify,
        patch("util.natural_language_geocoder._normalize_geometry_to_wkt") as mock_norm,
    ):
        mock_extract.return_value = Polygon([(0, 0), (1, 1), (1, 0), (0, 0)])
        mock_simplify.return_value = Polygon([(0, 0), (1, 1), (1, 0), (0, 0)])
        mock_norm.return_value = "POLYGON"
        convert_text_to_geom("test polygon")


def test_convert_text_to_geom_logging_multi_polygon():
    """Test logging properties of a MultiPolygon."""
    with (
        patch("util.natural_language_geocoder.extract_geometry_from_text") as mock_extract,
        patch("util.natural_language_geocoder.GeocodeIndexPlaceLookup"),
        patch("util.natural_language_geocoder.simplify_geometry") as mock_simplify,
        patch("util.natural_language_geocoder._normalize_geometry_to_wkt") as mock_norm,
    ):
        mock_extract.return_value = MultiPolygon([Polygon([(0, 0), (1, 1), (1, 0), (0, 0)])])
        mock_simplify.return_value = MultiPolygon([Polygon([(0, 0), (1, 1), (1, 0), (0, 0)])])
        mock_norm.return_value = "MULTIPOLYGON"
        convert_text_to_geom("test multi")
