"""Tests for the spatial utility module."""

from tests.conftest import generate_spatial_resolution_metadata
from util.spatial import (
    SpatialResolution,
    check_spatial_disambiguation,
    extract_spatial_resolution,
    group_by_spatial_resolution,
)


class TestExtractSpatialResolution:
    """Tests for extract_spatial_resolution function."""

    def test_extracts_gridded_resolution(self):
        """Test extraction from GriddedResolutions."""
        metadata = generate_spatial_resolution_metadata(1, 1, "Kilometers")

        result = extract_spatial_resolution(metadata)

        assert result is not None
        assert result.x_dimension == 1
        assert result.y_dimension == 1
        assert result.unit == "Kilometers"
        assert result.meters == 1000

    def test_extracts_non_gridded_resolution(self):
        """Test extraction from NonGriddedResolutions."""
        metadata = generate_spatial_resolution_metadata(
            500, 500, "Meters", resolution_type="NonGriddedResolutions"
        )

        result = extract_spatial_resolution(metadata)

        assert result is not None
        assert result.x_dimension == 500
        assert result.unit == "Meters"
        assert result.meters == 500

    def test_handles_varies_resolution(self):
        """Test handling of 'Varies' special value."""
        metadata = {
            "SpatialExtent": {
                "HorizontalSpatialDomain": {
                    "ResolutionAndCoordinateSystem": {
                        "HorizontalDataResolution": {"VariesResolution": "Varies"}
                    }
                }
            }
        }

        result = extract_spatial_resolution(metadata)

        assert result is not None
        assert result.unit == "Varies"
        assert result.meters == 0

    def test_handles_point_resolution(self):
        """Test handling of 'Point' special value."""
        metadata = {
            "SpatialExtent": {
                "HorizontalSpatialDomain": {
                    "ResolutionAndCoordinateSystem": {
                        "HorizontalDataResolution": {"PointResolution": "Point"}
                    }
                }
            }
        }

        result = extract_spatial_resolution(metadata)

        assert result is not None
        assert result.unit == "Point"

    def test_returns_none_when_no_resolution(self):
        """Test returns None when no resolution field."""
        metadata = {
            "SpatialExtent": {"HorizontalSpatialDomain": {"ResolutionAndCoordinateSystem": {}}}
        }

        result = extract_spatial_resolution(metadata)

        assert result is None

    def test_returns_none_when_no_spatial_extent(self):
        """Test returns None when no SpatialExtent."""
        metadata = {}

        result = extract_spatial_resolution(metadata)

        assert result is None

    def test_prefers_gridded_over_non_gridded(self):
        """Test that GriddedResolutions is preferred."""
        metadata = generate_spatial_resolution_metadata(1, 1, "Kilometers")
        # Add a competing NonGriddedResolutions entry
        horiz_res = metadata["SpatialExtent"]["HorizontalSpatialDomain"][
            "ResolutionAndCoordinateSystem"
        ]["HorizontalDataResolution"]
        horiz_res["NonGriddedResolutions"] = [
            {"XDimension": 500, "YDimension": 500, "Unit": "Meters"}
        ]

        result = extract_spatial_resolution(metadata)

        assert result is not None
        assert result.x_dimension == 1
        assert result.unit == "Kilometers"


class TestSpatialResolutionStr:
    """Tests for SpatialResolution __str__ method."""

    def test_kilometers_display(self):
        """Test display for kilometers."""
        resolution = SpatialResolution(x_dimension=1, y_dimension=1, unit="Kilometers", meters=1000)
        assert str(resolution) == "1 km"

    def test_meters_display(self):
        """Test display for meters."""
        resolution = SpatialResolution(x_dimension=250, y_dimension=250, unit="Meters", meters=250)
        assert str(resolution) == "250 m"

    def test_degrees_display(self):
        """Test display for decimal degrees."""
        resolution = SpatialResolution(
            x_dimension=0.25, y_dimension=0.25, unit="Decimal Degrees", meters=27830
        )
        assert str(resolution) == "0.25 deg"


class TestGroupBySpatialResolution:
    """Tests for group_by_spatial_resolution function."""

    def test_groups_by_resolution(self):
        """Test grouping collections by resolution."""
        collections = [
            generate_spatial_resolution_metadata(1, 1, "Kilometers"),
            generate_spatial_resolution_metadata(250, 250, "Meters"),
            generate_spatial_resolution_metadata(1, 1, "Kilometers"),
        ]

        groups = group_by_spatial_resolution(collections)

        assert len(groups) == 2
        assert len(groups["1 km"]) == 2
        assert len(groups["250 m"]) == 1

    def test_groups_none_for_missing_resolution(self):
        """Test that collections without resolution are grouped under None."""
        collections = [
            generate_spatial_resolution_metadata(1, 1, "Kilometers"),
            {"SpatialExtent": {}},
            {},
        ]

        groups = group_by_spatial_resolution(collections)

        assert len(groups) == 2
        assert len(groups["1 km"]) == 1
        assert len(groups[None]) == 2


class TestCheckSpatialDisambiguation:
    """Tests for check_spatial_disambiguation function."""

    def test_no_disambiguation_when_same_resolution(self):
        """Test no disambiguation needed when all have same resolution."""
        collections = [
            generate_spatial_resolution_metadata(1, 1, "Kilometers"),
            generate_spatial_resolution_metadata(1, 1, "Kilometers"),
        ]

        needs_disambiguation, resolutions = check_spatial_disambiguation(collections)

        assert needs_disambiguation is False
        assert resolutions == ["1 km"]

    def test_disambiguation_when_different_resolutions(self):
        """Test disambiguation needed when different resolutions."""
        collections = [
            generate_spatial_resolution_metadata(1, 1, "Kilometers"),
            generate_spatial_resolution_metadata(250, 250, "Meters"),
            generate_spatial_resolution_metadata(5, 5, "Kilometers"),
        ]

        needs_disambiguation, resolutions = check_spatial_disambiguation(collections)

        assert needs_disambiguation is True
        assert len(resolutions) == 3
        # Should be sorted by size (smallest first)
        assert resolutions[0] == "250 m"
        assert resolutions[1] == "1 km"
        assert resolutions[2] == "5 km"

    def test_ignores_varies_resolution(self):
        """Test that 'Varies' resolution is ignored for disambiguation."""
        collections = [
            generate_spatial_resolution_metadata(1, 1, "Kilometers"),
            {
                "SpatialExtent": {
                    "HorizontalSpatialDomain": {
                        "ResolutionAndCoordinateSystem": {
                            "HorizontalDataResolution": {"VariesResolution": "Varies"}
                        }
                    }
                }
            },
        ]

        needs_disambiguation, resolutions = check_spatial_disambiguation(collections)

        assert needs_disambiguation is False
        assert resolutions == ["1 km"]

    def test_no_disambiguation_when_no_resolutions(self):
        """Test no disambiguation when no collections have resolution."""
        collections = [
            {"SpatialExtent": {}},
            {},
        ]

        needs_disambiguation, resolutions = check_spatial_disambiguation(collections)

        assert needs_disambiguation is False
        assert resolutions == []

    def test_sorts_resolutions_by_size(self):
        """Test resolutions are sorted by size (smallest first)."""
        collections = [
            generate_spatial_resolution_metadata(0.25, 0.25, "Decimal Degrees"),
            generate_spatial_resolution_metadata(250, 250, "Meters"),
            generate_spatial_resolution_metadata(1, 1, "Kilometers"),
        ]

        _, resolutions = check_spatial_disambiguation(collections)

        # 250m < 1km < 0.25deg (~27km)
        assert resolutions == ["250 m", "1 km", "0.25 deg"]


class TestExtractSpatialExtent:
    """Tests for extract_spatial_extent function."""

    def test_extract_spatial_extent(self):
        """Test extracting spatial extent geometry."""
        from util.spatial import extract_spatial_extent

        # Test missing SpatialExtent
        assert extract_spatial_extent({}) == (None, False)

        # Test Point
        metadata = {
            "SpatialExtent": {
                "HorizontalSpatialDomain": {
                    "Geometry": {"Points": [{"Longitude": 10, "Latitude": 20}]}
                }
            }
        }
        res = extract_spatial_extent(metadata)
        assert res == (None, False)

        # Test BoundingRectangle
        metadata2 = {
            "SpatialExtent": {
                "HorizontalSpatialDomain": {
                    "Geometry": {
                        "BoundingRectangles": [
                            {
                                "WestBoundingCoordinate": -10,
                                "EastBoundingCoordinate": 10,
                                "SouthBoundingCoordinate": -20,
                                "NorthBoundingCoordinate": 20,
                            }
                        ]
                    }
                }
            }
        }
        res2 = extract_spatial_extent(metadata2)
        assert "POLYGON" in res2[0]
        assert res2[1] is False

        # Test Global BoundingRectangle
        metadata_global = {
            "SpatialExtent": {
                "HorizontalSpatialDomain": {
                    "Geometry": {
                        "BoundingRectangles": [
                            {
                                "WestBoundingCoordinate": -180,
                                "EastBoundingCoordinate": 180,
                                "SouthBoundingCoordinate": -90,
                                "NorthBoundingCoordinate": 90,
                            }
                        ]
                    }
                }
            }
        }
        res_global = extract_spatial_extent(metadata_global)
        assert "POLYGON" in res_global[0]
        assert res_global[1] is True


class TestSpatialResolutionSortKey:
    """Tests for _spatial_resolution_sort_key function."""

    def test_spatial_resolution_sort_key(self):
        """Test sort key logic."""
        from util.spatial import _spatial_resolution_sort_key

        assert _spatial_resolution_sort_key("invalid") == float("inf")
        assert _spatial_resolution_sort_key("not_a_number km") == float("inf")
        assert _spatial_resolution_sort_key("1 km") == 1000.0
        assert _spatial_resolution_sort_key("250 m") == 250.0
        assert _spatial_resolution_sort_key("0.25 deg") == 27830.0


class TestParseSpatialResolutionFromTitle:
    """Tests for parse_spatial_resolution_from_title function."""

    def test_parse_spatial_resolution_from_title(self):
        """Test parsing resolution from title."""
        from util.spatial import parse_spatial_resolution_from_title

        assert parse_spatial_resolution_from_title("Product 1km") == {
            "XDimension": 1.0,
            "YDimension": 1.0,
            "Unit": "Kilometers",
        }
        assert parse_spatial_resolution_from_title("Product 250m") == {
            "XDimension": 250.0,
            "YDimension": 250.0,
            "Unit": "Meters",
        }
        assert parse_spatial_resolution_from_title("Product 0.25 deg") == {
            "XDimension": 0.25,
            "YDimension": 0.25,
            "Unit": "Decimal Degrees",
        }
        assert parse_spatial_resolution_from_title("Product 0.25deg") == {
            "XDimension": 0.25,
            "YDimension": 0.25,
            "Unit": "Decimal Degrees",
        }
        assert parse_spatial_resolution_from_title("Product 2000m") is None
        assert parse_spatial_resolution_from_title("Product something") is None

    def test_extract_gpolygon(self):
        """Test extraction of GPolygons."""
        from util.spatial import extract_spatial_extent

        metadata = {
            "SpatialExtent": {
                "HorizontalSpatialDomain": {
                    "Geometry": {
                        "GPolygons": [
                            {
                                "Boundary": {
                                    "Points": [
                                        {"Longitude": 0, "Latitude": 0},
                                        {"Longitude": 10, "Latitude": 0},
                                        {"Longitude": 10, "Latitude": 10},
                                        {"Longitude": 0, "Latitude": 10},
                                        {"Longitude": 0, "Latitude": 0},
                                    ]
                                }
                            }
                        ]
                    }
                }
            }
        }
        res = extract_spatial_extent(metadata)
        assert "POLYGON((0 0, 10 0" in res[0]
        assert res[1] is False
