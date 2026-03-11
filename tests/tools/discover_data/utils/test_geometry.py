"""Tests for generic geometry utilities."""

from models.tools.discover_data import SpatialConstraint
from tools.discover_data.utils.earthdata_search_links import _earthdata_search_link
from util.geometry import _bbox_from_wkt, _map_center_zoom, _round_bbox


class TestRoundBbox:
    """Tests for _round_bbox helper."""

    def test_rounds_coordinates_to_five_decimals(self):
        """Each coordinate should be rounded to 5 decimal places."""
        result = _round_bbox("-92.359312345,30.365023456,-77.909553456,45.563671234")
        assert result == "-92.35931,30.36502,-77.90955,45.56367"

    def test_preserves_exact_values(self):
        """Coordinates already within 5 decimals should be unchanged."""
        assert _round_bbox("-10.0,20.0,30.0,60.0") == "-10.0,20.0,30.0,60.0"

    def test_rounds_negative_coordinates(self):
        """Should round negative values correctly."""
        result = _round_bbox("-180.123456,-90.123456,180.123456,90.123456")
        assert result == "-180.12346,-90.12346,180.12346,90.12346"

    def test_earthdata_search_sb_param_is_rounded(self):
        """The sb[0]= value in an EDS link should be rounded to 5 decimal places."""
        spatial = SpatialConstraint(
            wkt_geometry="POLYGON((-92.35931234 30.36502345, -77.90955345 30.36502345, -77.90955345 45.56367123, -92.35931234 45.56367123, -92.35931234 30.36502345))"
        )
        link = _earthdata_search_link("C1-P", spatial=spatial)
        # Extract just the sb[0]= value and check its coordinates are ≤5 decimal places
        import re

        sb_match = re.search(r"sb\[0\]=([^&]+)", link["url"])
        assert sb_match, "sb[0]= param not found in URL"
        coords = re.findall(r"-?\d+\.\d+", sb_match.group(1))
        for coord in coords:
            assert len(coord.split(".")[1]) <= 5, f"{coord} has more than 5 decimal places"


# ---------------------------------------------------------------------------
# _map_center_zoom
# ---------------------------------------------------------------------------


class TestMapCenterZoom:
    """Tests for _map_center_zoom helper."""

    def test_returns_correct_center_lat(self):
        """Center latitude should be the midpoint of south and north."""
        lat, _lon, _zoom = _map_center_zoom("-10.0,20.0,30.0,50.0")
        assert lat == 35.0

    def test_returns_correct_center_lon(self):
        """Center longitude should be the midpoint of west and east."""
        _lat, lon, _zoom = _map_center_zoom("-10.0,20.0,30.0,50.0")
        assert lon == 10.0

    def test_zoom_is_positive(self):
        """Zoom should be a positive float for any valid bbox."""
        _lat, _lon, zoom = _map_center_zoom("-180.0,-90.0,180.0,90.0")
        assert zoom > 0

    def test_smaller_bbox_gives_higher_zoom(self):
        """A tighter bbox should produce a higher zoom level than a large one."""
        _l, _n, zoom_large = _map_center_zoom("-180.0,-90.0,180.0,90.0")
        _l, _n, zoom_small = _map_center_zoom("-5.0,45.0,5.0,55.0")
        assert zoom_small > zoom_large

    def test_point_bbox_does_not_raise(self):
        """A zero-area bbox (point) should not raise ZeroDivisionError."""
        lat, lon, zoom = _map_center_zoom("10.0,20.0,10.0,20.0")
        assert lat == 20.0
        assert lon == 10.0
        assert zoom > 0

    def test_antimeridian_bbox_uses_wrapped_lon_center(self):
        """For east < west, center longitude should wrap into -180..180."""
        lat, lon, _zoom = _map_center_zoom("170.0,-10.0,-170.0,10.0")
        assert lat == 0.0
        assert lon == -180.0

    def test_antimeridian_bbox_uses_wrapped_span_for_zoom(self):
        """Wrapped longitudinal span should drive a tighter zoom than naive 340° span."""
        _lat, _lon, zoom_crossing = _map_center_zoom("170.0,-5.0,-170.0,5.0")
        _lat, _lon, zoom_non_crossing = _map_center_zoom("-170.0,-5.0,170.0,5.0")
        assert zoom_crossing > zoom_non_crossing


# ---------------------------------------------------------------------------
# _bbox_from_wkt
# ---------------------------------------------------------------------------


class TestBboxFromWkt:
    """Tests for _bbox_from_wkt helper."""

    def test_extracts_bbox_from_polygon(self):
        """Should return west,south,east,north from a simple polygon."""
        wkt = "POLYGON((-10 20, 30 20, 30 60, -10 60, -10 20))"
        assert _bbox_from_wkt(wkt) == "-10.0,20.0,30.0,60.0"

    def test_extracts_bbox_from_point(self):
        """A point WKT should produce a degenerate bbox with equal min/max."""
        wkt = "POINT(-104.9 39.7)"
        assert _bbox_from_wkt(wkt) == "-104.9,39.7,-104.9,39.7"

    def test_returns_none_for_invalid_wkt(self):
        """Should return None when no coordinate pairs can be parsed."""
        assert _bbox_from_wkt("NOT_A_WKT") is None

    def test_returns_none_for_empty_string(self):
        """Should return None for an empty string."""
        assert _bbox_from_wkt("") is None

    def test_handles_negative_coordinates(self):
        """Should correctly handle negative longitudes and latitudes."""
        wkt = "POLYGON((-180 -90, 180 -90, 180 90, -180 90, -180 -90))"
        assert _bbox_from_wkt(wkt) == "-180.0,-90.0,180.0,90.0"
