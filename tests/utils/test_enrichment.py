"""Tests for the enrichment utility module."""

from datetime import UTC, datetime

from shapely import wkt

from tests.conftest import GLOBAL_BOUNDING_BOX, generate_spatial_resolution_metadata
from util.enrichment import enrich_collection_metadata
from util.spatial import extract_spatial_extent, parse_spatial_resolution_from_title
from util.temporal import extract_temporal_extent, parse_temporal_resolution_from_title


class TestExtractTemporalExtent:
    """Tests for extract_temporal_extent function."""

    def test_extracts_range_date_times(self):
        """Test extraction from RangeDateTimes."""
        metadata = {
            "TemporalExtents": [
                {
                    "RangeDateTimes": [
                        {
                            "BeginningDateTime": "2000-02-24T00:00:00Z",
                            "EndingDateTime": "2020-12-31T23:59:59Z",
                        }
                    ]
                }
            ]
        }

        start, end, is_ongoing = extract_temporal_extent(metadata)

        assert start == datetime(2000, 2, 24, 0, 0, 0, tzinfo=UTC)
        assert end == datetime(2020, 12, 31, 23, 59, 59, tzinfo=UTC)
        assert is_ongoing is False

    def test_extracts_single_date_times(self):
        """Test extraction from SingleDateTimes."""
        metadata = {
            "TemporalExtents": [
                {
                    "SingleDateTimes": [
                        "2015-01-01T00:00:00Z",
                        "2015-06-15T00:00:00Z",
                        "2015-12-31T00:00:00Z",
                    ]
                }
            ]
        }

        start, end, is_ongoing = extract_temporal_extent(metadata)

        assert start == datetime(2015, 1, 1, 0, 0, 0, tzinfo=UTC)
        assert end == datetime(2015, 12, 31, 0, 0, 0, tzinfo=UTC)
        assert is_ongoing is False

    def test_ongoing_when_no_end_date(self):
        """Test that is_ongoing is True when no end date."""
        metadata = {
            "TemporalExtents": [
                {
                    "RangeDateTimes": [
                        {
                            "BeginningDateTime": "2000-02-24T00:00:00Z",
                        }
                    ]
                }
            ]
        }

        start, end, is_ongoing = extract_temporal_extent(metadata)

        assert start is not None
        assert end is None
        assert is_ongoing is True

    def test_ongoing_when_ends_at_present_flag(self):
        """Test that EndsAtPresentFlag sets is_ongoing."""
        metadata = {
            "TemporalExtents": [
                {
                    "EndsAtPresentFlag": True,
                    "RangeDateTimes": [
                        {
                            "BeginningDateTime": "2000-02-24T00:00:00Z",
                            "EndingDateTime": "2020-12-31T23:59:59Z",
                        }
                    ],
                }
            ]
        }

        _, _, is_ongoing = extract_temporal_extent(metadata)

        assert is_ongoing is True

    def test_empty_temporal_extents(self):
        """Test handling of empty TemporalExtents."""
        metadata = {"TemporalExtents": []}

        start, end, is_ongoing = extract_temporal_extent(metadata)

        assert start is None
        assert end is None
        assert is_ongoing is False

    def test_missing_temporal_extents(self):
        """Test handling of missing TemporalExtents."""
        metadata = {}

        start, end, is_ongoing = extract_temporal_extent(metadata)

        assert start is None
        assert end is None
        assert is_ongoing is False


class TestExtractSpatialExtent:
    """Tests for extract_spatial_extent function."""

    def test_extracts_bounding_rectangle(self):
        """Test extraction from BoundingRectangles."""
        metadata = {
            "SpatialExtent": {
                "HorizontalSpatialDomain": {
                    "Geometry": {
                        "BoundingRectangles": [
                            {
                                "WestBoundingCoordinate": -125.0,
                                "EastBoundingCoordinate": -65.0,
                                "NorthBoundingCoordinate": 50.0,
                                "SouthBoundingCoordinate": 24.0,
                            }
                        ]
                    }
                }
            }
        }

        wkt_str, is_global = extract_spatial_extent(metadata)

        assert wkt_str is not None
        assert is_global is False

        # Parse and validate the WKT
        polygon = wkt.loads(wkt_str)
        assert polygon.geom_type == "Polygon"
        assert polygon.is_valid

        # Check bounds match input coordinates
        minx, miny, maxx, maxy = polygon.bounds
        assert minx == -125.0
        assert maxx == -65.0
        assert miny == 24.0
        assert maxy == 50.0

    def test_extracts_gpolygon(self):
        """Test extraction from GPolygons."""
        metadata = {
            "SpatialExtent": {
                "HorizontalSpatialDomain": {
                    "Geometry": {
                        "GPolygons": [
                            {
                                "Boundary": {
                                    "Points": [
                                        {"Longitude": -122.0, "Latitude": 37.0},
                                        {"Longitude": -121.0, "Latitude": 37.0},
                                        {"Longitude": -121.0, "Latitude": 38.0},
                                        {"Longitude": -122.0, "Latitude": 38.0},
                                        {"Longitude": -122.0, "Latitude": 37.0},
                                    ]
                                }
                            }
                        ]
                    }
                }
            }
        }

        wkt_str, is_global = extract_spatial_extent(metadata)

        assert wkt_str is not None
        assert is_global is False

        # Parse and validate the WKT
        polygon = wkt.loads(wkt_str)
        assert polygon.geom_type == "Polygon"
        assert polygon.is_valid

        # Check bounds match input coordinates
        minx, miny, maxx, maxy = polygon.bounds
        assert minx == -122.0
        assert maxx == -121.0
        assert miny == 37.0
        assert maxy == 38.0

    def test_prefers_gpolygon_over_bounding_rectangle(self):
        """Test that GPolygons are preferred over BoundingRectangles."""
        metadata = {
            "SpatialExtent": {
                "HorizontalSpatialDomain": {
                    "Geometry": {
                        "GPolygons": [
                            {
                                "Boundary": {
                                    "Points": [
                                        {"Longitude": -122.0, "Latitude": 37.0},
                                        {"Longitude": -121.0, "Latitude": 37.0},
                                        {"Longitude": -121.0, "Latitude": 38.0},
                                        {"Longitude": -122.0, "Latitude": 37.0},
                                    ]
                                }
                            }
                        ],
                        "BoundingRectangles": [
                            {
                                "WestBoundingCoordinate": -180.0,
                                "EastBoundingCoordinate": 180.0,
                                "NorthBoundingCoordinate": 90.0,
                                "SouthBoundingCoordinate": -90.0,
                            }
                        ],
                    }
                }
            }
        }

        wkt_str, is_global = extract_spatial_extent(metadata)

        assert is_global is False

        # Parse and validate - should use GPolygon, not bounding rectangle
        polygon = wkt.loads(wkt_str)
        minx, miny, maxx, maxy = polygon.bounds

        # GPolygon bounds: -122 to -121, 37 to 38
        # BoundingRect bounds would be: -180 to 180, -90 to 90
        assert minx == -122.0
        assert maxx == -121.0
        assert miny == 37.0
        # Note: max lat is 37.0 because the polygon is a triangle (point 4 = point 1)
        assert maxy == 38.0

    def test_detects_global_coverage(self):
        """Test detection of global coverage."""
        metadata = {
            "SpatialExtent": {
                "HorizontalSpatialDomain": {
                    "Geometry": {"BoundingRectangles": [GLOBAL_BOUNDING_BOX]}
                }
            }
        }

        _, is_global = extract_spatial_extent(metadata)

        assert is_global is True

    def test_empty_geometry(self):
        """Test handling of empty geometry."""
        metadata = {"SpatialExtent": {"HorizontalSpatialDomain": {"Geometry": {}}}}

        wkt, is_global = extract_spatial_extent(metadata)

        assert wkt is None
        assert is_global is False

    def test_missing_spatial_extent(self):
        """Test handling of missing SpatialExtent."""
        metadata = {}

        wkt, is_global = extract_spatial_extent(metadata)

        assert wkt is None
        assert is_global is False


class TestParseTemporalResolutionFromTitle:
    """Tests for parse_temporal_resolution_from_title function."""

    def test_parses_daily(self):
        """Test parsing 'Daily' from title."""
        title = "MODIS/Terra Land Surface Temperature Daily L3 Global 1km"

        result = parse_temporal_resolution_from_title(title)

        assert result == {"Value": 1, "Unit": "Day"}

    def test_parses_monthly(self):
        """Test parsing 'Monthly' from title."""
        title = "GPM Monthly Precipitation"

        result = parse_temporal_resolution_from_title(title)

        assert result == {"Value": 1, "Unit": "Month"}

    def test_parses_8_day(self):
        """Test parsing '8-Day' from title."""
        title = "MODIS/Terra Vegetation Indices 8-Day L3 Global 250m"

        result = parse_temporal_resolution_from_title(title)

        assert result == {"Value": 8, "Unit": "Day"}

    def test_parses_hourly(self):
        """Test parsing 'Hourly' from title."""
        title = "MERRA-2 Hourly Diagnostics"

        result = parse_temporal_resolution_from_title(title)

        assert result == {"Value": 1, "Unit": "Hour"}

    def test_parses_12_hourly_with_space(self):
        """Test parsing '12 Hourly' (with space) from title."""
        title = "12 Hourly Interpolated Surface Air Pressure from Buoys"

        result = parse_temporal_resolution_from_title(title)

        assert result == {"Value": 12, "Unit": "Hour"}

    def test_parses_12_hourly_with_hyphen(self):
        """Test parsing '12-Hourly' (with hyphen) from title."""
        title = "12-Hourly Interpolated Surface Position from Buoys"

        result = parse_temporal_resolution_from_title(title)

        assert result == {"Value": 12, "Unit": "Hour"}

    def test_returns_none_for_no_resolution(self):
        """Test returns None when no resolution found."""
        title = "MODIS/Terra Land Surface Temperature L3 Global 1km"

        result = parse_temporal_resolution_from_title(title)

        assert result is None


class TestParseSpatialResolutionFromTitle:
    """Tests for parse_spatial_resolution_from_title function."""

    def test_parses_km(self):
        """Test parsing 'km' resolution from title."""
        title = "MODIS/Terra Land Surface Temperature Daily L3 Global 1km"

        result = parse_spatial_resolution_from_title(title)

        assert result == {"XDimension": 1.0, "YDimension": 1.0, "Unit": "Kilometers"}

    def test_parses_m(self):
        """Test parsing 'm' resolution from title."""
        title = "MODIS/Terra Vegetation Indices 8-Day L3 Global 250m"

        result = parse_spatial_resolution_from_title(title)

        assert result == {"XDimension": 250.0, "YDimension": 250.0, "Unit": "Meters"}

    def test_parses_degree(self):
        """Test parsing 'degree' resolution from title."""
        title = "Global 0.25 Degree Precipitation"

        result = parse_spatial_resolution_from_title(title)

        assert result == {"XDimension": 0.25, "YDimension": 0.25, "Unit": "Decimal Degrees"}

    def test_skips_year_like_numbers(self):
        """Test that year-like numbers are skipped."""
        title = "MODIS Collection 2000 Data Product"

        result = parse_spatial_resolution_from_title(title)

        assert result is None

    def test_returns_none_for_no_resolution(self):
        """Test returns None when no resolution found."""
        title = "MODIS/Terra Land Surface Temperature"

        result = parse_spatial_resolution_from_title(title)

        assert result is None


class TestEnrichMetadata:
    """Tests for enrich_collection_metadata function."""

    def test_enriches_temporal_resolution_from_title(self):
        """Test that temporal resolution is enriched from title when missing."""
        metadata = {
            "EntryTitle": "MODIS/Terra Land Surface Temperature Daily L3 Global 1km",
            "TemporalExtents": [
                {"RangeDateTimes": [{"BeginningDateTime": "2000-02-24T00:00:00Z"}]}
            ],
        }

        enriched = enrich_collection_metadata(metadata)

        assert "TemporalResolution" in enriched["TemporalExtents"][0]
        assert enriched["TemporalExtents"][0]["TemporalResolution"]["Value"] == 1
        assert enriched["TemporalExtents"][0]["TemporalResolution"]["Unit"] == "Day"

    def test_preserves_existing_temporal_resolution(self):
        """Test that existing temporal resolution is not overwritten."""
        metadata = {
            "EntryTitle": "MODIS/Terra Land Surface Temperature Daily L3 Global 1km",
            "TemporalExtents": [
                {
                    "TemporalResolution": {"Value": 8, "Unit": "Day"},
                    "RangeDateTimes": [{"BeginningDateTime": "2000-02-24T00:00:00Z"}],
                }
            ],
        }

        enriched = enrich_collection_metadata(metadata)

        # Should preserve the original 8-Day, not override with Daily from title
        assert enriched["TemporalExtents"][0]["TemporalResolution"]["Value"] == 8

    def test_enriches_spatial_resolution_from_title(self):
        """Test that spatial resolution is enriched from title when missing."""
        metadata = {
            "EntryTitle": "MODIS/Terra Land Surface Temperature Daily L3 Global 1km",
            "SpatialExtent": {"HorizontalSpatialDomain": {}},
        }

        enriched = enrich_collection_metadata(metadata)

        horiz_res = enriched["SpatialExtent"]["HorizontalSpatialDomain"][
            "ResolutionAndCoordinateSystem"
        ]["HorizontalDataResolution"]
        assert "GriddedResolutions" in horiz_res
        assert horiz_res["GriddedResolutions"][0]["XDimension"] == 1.0
        assert horiz_res["GriddedResolutions"][0]["Unit"] == "Kilometers"

    def test_preserves_existing_spatial_resolution(self):
        """Test that existing spatial resolution is not overwritten."""
        metadata = generate_spatial_resolution_metadata(500, 500, "Meters")
        metadata["EntryTitle"] = "MODIS/Terra Land Surface Temperature Daily L3 Global 1km"

        enriched = enrich_collection_metadata(metadata)

        # Should preserve the original 500m, not override with 1km from title
        horiz_res = enriched["SpatialExtent"]["HorizontalSpatialDomain"][
            "ResolutionAndCoordinateSystem"
        ]["HorizontalDataResolution"]
        assert horiz_res["GriddedResolutions"][0]["XDimension"] == 500

    def test_does_not_modify_original_metadata(self):
        """Test that original metadata is not modified."""
        metadata = {
            "EntryTitle": "MODIS/Terra Daily 1km",
            "TemporalExtents": [{}],
        }

        enriched = enrich_collection_metadata(metadata)

        # Original should not have TemporalResolution
        assert "TemporalResolution" not in metadata["TemporalExtents"][0]
        # Enriched should have it
        assert "TemporalResolution" in enriched["TemporalExtents"][0]
