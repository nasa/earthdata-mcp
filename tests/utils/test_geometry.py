"""Tests for util.geometry."""

from util.geometry import _bbox_from_wkt, _map_center_zoom, _round_bbox


def test_bbox_from_wkt():
    """Test function."""
    wkt = "POLYGON((-10.0 -10.0, 10.0 -10.0, 10.0 10.0, -10.0 10.0, -10.0 -10.0))"
    assert _bbox_from_wkt(wkt) == "-10.0,-10.0,10.0,10.0"


def test_bbox_from_wkt_invalid():
    """Test function."""
    assert _bbox_from_wkt("INVALID") is None


def test_round_bbox():
    """Test function."""
    bbox = "-10.123456,-10.123456,10.123456,10.123456"
    assert _round_bbox(bbox, 2) == "-10.12,-10.12,10.12,10.12"


def test_map_center_zoom_normal():
    """Test function."""
    bbox = "-10,-10,10,10"
    lat, lon, zoom = _map_center_zoom(bbox)
    assert lat == 0.0
    assert lon == 0.0
    # span is 20. 360/20 = 18. log2(18) = 4.1699. + 1 = 5.1699
    assert abs(zoom - 5.1699) < 0.001


def test_map_center_zoom_antimeridian():
    """Test function."""
    # west=170, east=-170
    bbox = "170,-10,-170,10"
    lat, lon, zoom = _map_center_zoom(bbox)
    assert lat == 0.0
    assert lon == -180.0
    # span is 20
    assert abs(zoom - 5.1699) < 0.001


def test_map_center_zoom_zero_area():
    """Test function."""
    bbox = "10,10,10,10"
    lat, lon, zoom = _map_center_zoom(bbox)
    assert lat == 10.0
    assert lon == 10.0
    # span is 0, max_span uses 0.001. 360/0.001 = 360000. log2(360000) = 18.4576 + 1 = 19.4576
    assert abs(zoom - 19.4576) < 0.001
