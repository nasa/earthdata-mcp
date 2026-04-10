"""Tests for util.cmr.search_tools helpers."""

from datetime import UTC, datetime

import pytest

from util.cmr.search_tools import (
    _count_geometry_points,
    _dedupe_strings,
    _extract_collection_spatial_resolution,
    _extract_collection_temporal_resolution,
    _extract_granule_archive_info,
    _extract_granule_bounding_box,
    build_spatial_files,
    extract_access_urls,
    extract_granule_temporal_extent,
    format_cloud_cover_range,
    format_temporal_range,
    normalize_collection_item,
    normalize_granule_item,
)


def test_build_spatial_files_raises_value_error_for_invalid_wkt():
    """Malformed WKT should be normalized to ValueError."""
    with pytest.raises(ValueError, match="Invalid WKT geometry"):
        build_spatial_files("POINT((1 2))")


def test_format_temporal_range_returns_none_when_bounds_missing():
    """Temporal formatter should return None when both bounds are absent."""
    assert format_temporal_range(None, None) is None


def test_format_temporal_range_accepts_datetimes_and_strings():
    """Temporal formatter should support mixed datetime and ISO string inputs."""
    start = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
    end = "2024-01-31T23:59:59Z"

    assert format_temporal_range(start, end) == "2024-01-01T00:00:00Z,2024-01-31T23:59:59Z"


def test_format_temporal_range_handles_open_start_bound():
    """Temporal formatter should preserve open start bounds as empty prefix."""
    assert format_temporal_range(None, "2024-01-31T23:59:59Z") == ",2024-01-31T23:59:59Z"


def test_format_temporal_range_rejects_invalid_type():
    """Temporal formatter should reject unsupported input types."""
    with pytest.raises(ValueError, match="temporal_start_date"):
        format_temporal_range(123, None)


def test_format_temporal_range_rejects_invalid_iso_string():
    """Temporal formatter should reject invalid ISO-8601 values."""
    with pytest.raises(ValueError, match="temporal_end_date"):
        format_temporal_range(None, "not-an-iso-time")


def test_build_spatial_files_returns_none_for_empty_input():
    """Spatial file builder should return None when no geometry is provided."""
    assert build_spatial_files(None) is None


def test_build_spatial_files_rejects_too_many_points():
    """Spatial file builder should reject geometries above CMR point limits."""
    # 5001 coordinates exceeds CMR's 5000-point upload limit.
    coords = ", ".join(f"{i} 0" for i in range(5001))
    with pytest.raises(ValueError, match="exceeding the CMR shapefile limit"):
        build_spatial_files(f"LINESTRING({coords})")


def test_build_spatial_files_repairs_invalid_geometry():
    """Spatial file builder should repair invalid but recoverable polygon geometry."""
    files = build_spatial_files("POLYGON((0 0, 2 2, 2 0, 0 2, 0 0))")

    assert files is not None
    assert "shapefile" in files


def test_build_spatial_files_rejects_payload_over_limit(monkeypatch):
    """Spatial file builder should reject payloads larger than CMR byte limits."""
    monkeypatch.setattr("util.cmr.search_tools._CMR_MAX_BYTES", 10)

    with pytest.raises(ValueError, match="exceeding the CMR limit"):
        build_spatial_files("POINT(1 2)")


def test_count_geometry_points_polygon_and_multi_polygon():
    """Point counting helper should handle polygon and multipolygon geometries."""
    polygon_file = build_spatial_files("POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))")
    multi_file = build_spatial_files(
        "MULTIPOLYGON(((0 0, 1 0, 1 1, 0 1, 0 0)),((2 2, 3 2, 3 3, 2 3, 2 2)))"
    )

    assert polygon_file is not None
    assert multi_file is not None


def test_count_geometry_points_returns_zero_for_unknown_geom_type():
    """Point counting helper should return zero for unrecognized geometry types."""

    class UnknownGeometry:
        """Minimal stub geometry with an unknown geom_type for branch coverage."""

        geom_type = "Unknown"

    assert _count_geometry_points(UnknownGeometry()) == 0


def test_extract_granule_temporal_extent_supports_range_date_times():
    """Granule temporal extraction should merge multiple RangeDateTimes bounds."""
    umm = {
        "TemporalExtent": {
            "RangeDateTimes": [
                {
                    "BeginningDateTime": "2024-01-02T00:00:00Z",
                    "EndingDateTime": "2024-01-05T00:00:00Z",
                },
                {
                    "BeginningDateTime": "2024-01-01T00:00:00Z",
                    "EndingDateTime": "2024-01-07T00:00:00Z",
                },
            ]
        }
    }

    start, end = extract_granule_temporal_extent(umm)

    assert start == datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
    assert end == datetime(2024, 1, 7, 0, 0, tzinfo=UTC)


def test_extract_access_urls_filters_and_dedupes():
    """Access URL extraction should filter irrelevant URLs and preserve unique order."""
    umm = {
        "OnlineAccessURLs": [
            "https://example.com/a",
            {"URL": "https://example.com/a"},
            {"URLValue": "https://example.com/b"},
        ],
        "RelatedUrls": [
            "not-a-dict",
            {
                "URL": "https://example.com/c",
                "URLContentType": "DistributionURL",
                "Type": "VIEW RELATED INFORMATION",
            },
            {"Type": "GET DATA"},
            {
                "URLValue": "https://example.com/d",
                "URLContentType": "NotDistribution",
                "Type": "DOWNLOAD SOFTWARE",
            },
            {
                "URL": "https://example.com/ignore",
                "URLContentType": "NotDistribution",
                "Type": "VIEW RELATED INFORMATION",
            },
        ],
    }

    assert extract_access_urls(umm) == [
        "https://example.com/a",
        "https://example.com/b",
        "https://example.com/c",
        "https://example.com/d",
    ]


def test_normalize_collection_item_handles_missing_optional_fields():
    """Collection normalizer should provide safe defaults for missing optional fields."""
    normalized = normalize_collection_item(
        {"meta": {"concept-id": "C1"}, "umm": {"ShortName": "SN"}}
    )

    assert normalized["concept_id"] == "C1"
    assert normalized["entry_title"] == "SN"
    assert normalized["version"] is None
    assert not normalized["platforms"]
    assert not normalized["instruments"]


def test_normalize_granule_item_falls_back_to_umm_collection_concept_id():
    """Granule normalizer should fall back to UMM collection concept id when needed."""
    normalized = normalize_granule_item(
        {
            "meta": {"concept-id": "G1", "native-id": "N1"},
            "umm": {"CollectionConceptId": "C-UMM"},
        }
    )

    assert normalized["concept_id"] == "G1"
    assert normalized["collection_concept_id"] == "C-UMM"
    assert normalized["granule_ur"] == "N1"


def test_dedupe_strings_removes_empty_and_preserves_order():
    """String dedupe helper should drop empties and keep first-seen order."""
    assert _dedupe_strings(["a", "", "b", "a", "b", "c"]) == ["a", "b", "c"]


# --- format_cloud_cover_range tests ---


def test_format_cloud_cover_range_returns_none_when_both_none():
    """Cloud cover formatter should return None when neither bound is set."""
    assert format_cloud_cover_range(None, None) is None


def test_format_cloud_cover_range_both_bounds():
    """Cloud cover formatter should produce 'min,max' when both are set."""
    assert format_cloud_cover_range(10, 50) == "10,50"


def test_format_cloud_cover_range_max_only():
    """Cloud cover formatter should produce ',max' when only max is set."""
    assert format_cloud_cover_range(None, 20) == ",20"


def test_format_cloud_cover_range_min_only():
    """Cloud cover formatter should produce 'min,' when only min is set."""
    assert format_cloud_cover_range(80, None) == "80,"


def test_format_cloud_cover_range_handles_floats():
    """Cloud cover formatter should preserve fractional values."""
    assert format_cloud_cover_range(10.5, 75.3) == "10.5,75.3"


def test_format_cloud_cover_range_renders_whole_floats_as_ints():
    """Cloud cover formatter should render 20.0 as '20', not '20.0'."""
    assert format_cloud_cover_range(0.0, 100.0) == "0,100"


# --- _extract_granule_bounding_box tests ---


def test_extract_granule_bounding_box_returns_none_if_missing():
    """Should return None if UMM-G has no SpatialExtent."""
    assert _extract_granule_bounding_box({}) is None


def test_extract_granule_bounding_box_aggregates_multiple_rects():
    """Should compute the MBR across all valid bounding rectangles."""
    umm = {
        "SpatialExtent": {
            "HorizontalSpatialDomain": {
                "Geometry": {
                    "BoundingRectangles": [
                        {
                            "WestBoundingCoordinate": -10.0,
                            "SouthBoundingCoordinate": 20.0,
                            "EastBoundingCoordinate": -5.0,
                            "NorthBoundingCoordinate": 30.0,
                        },
                        {
                            "WestBoundingCoordinate": -15.0,
                            "SouthBoundingCoordinate": 25.0,
                            "EastBoundingCoordinate": -2.0,
                            "NorthBoundingCoordinate": 40.0,
                        },
                        "invalid-string-ignored",
                        {
                            "WestBoundingCoordinate": "not-a-float",
                            "SouthBoundingCoordinate": 20.0,
                            "EastBoundingCoordinate": -5.0,
                            "NorthBoundingCoordinate": 30.0,
                        },
                    ]
                }
            }
        }
    }
    mbr = _extract_granule_bounding_box(umm)
    assert mbr == [-15.0, 20.0, -2.0, 40.0]


def test_extract_granule_bounding_box_safely_handles_bad_data():
    """Should safely ignore malformed data types in the spatial tree."""
    # HorizontalSpatialDomain is a string, not a dict
    umm = {"SpatialExtent": {"HorizontalSpatialDomain": "invalid"}}
    assert _extract_granule_bounding_box(umm) is None

    # BoundingRectangles is a dict, not a list
    umm = {"SpatialExtent": {"HorizontalSpatialDomain": {"Geometry": {"BoundingRectangles": {}}}}}
    assert _extract_granule_bounding_box(umm) is None


# --- Extraction Helper Tests ---


def test_extract_collection_temporal_resolution():
    """Test temporal resolution extraction handles lists and single objects safely."""
    # Happy path: List of Resolutions
    assert (
        _extract_collection_temporal_resolution(
            {"TemporalExtents": [{"TemporalResolutions": [{"Value": 8, "Unit": "Day"}]}]}
        )
        == "8 Day"
    )

    # Happy path: Single Object Resolution (e.g. HLSL30)
    assert (
        _extract_collection_temporal_resolution(
            {"TemporalExtents": [{"TemporalResolution": {"Value": 1, "Unit": "Month"}}]}
        )
        == "1 Month"
    )

    # Missing data returns None
    assert _extract_collection_temporal_resolution({}) is None

    # Malformed data (string instead of list) returns None safely
    assert _extract_collection_temporal_resolution({"TemporalExtents": "Not a list"}) is None


def test_extract_collection_spatial_resolution():
    """Test spatial resolution extraction handles dimensions and missing data safely."""
    # Happy path: 2D Gridded Resolution
    assert (
        _extract_collection_spatial_resolution(
            {
                "SpatialExtent": {
                    "HorizontalSpatialDomain": {
                        "ResolutionAndCoordinateSystem": {
                            "HorizontalDataResolution": {
                                "GriddedResolutions": [
                                    {"XDimension": 30, "YDimension": 30, "Unit": "Meters"}
                                ]
                            }
                        }
                    }
                }
            }
        )
        == "30x30 Meters"
    )

    # Happy path: 1D Generic Resolution
    assert (
        _extract_collection_spatial_resolution(
            {
                "SpatialExtent": {
                    "HorizontalSpatialDomain": {
                        "ResolutionAndCoordinateSystem": {
                            "HorizontalDataResolution": {
                                "GenericResolutions": {"XDimension": 1, "Unit": "Kilometers"}
                            }
                        }
                    }
                }
            }
        )
        == "1 Kilometers"
    )

    # Missing data returns None
    assert _extract_collection_spatial_resolution({}) is None

    # Malformed data (string instead of dict) returns None safely
    assert _extract_collection_spatial_resolution({"SpatialExtent": "Not a dict"}) is None


def test_extract_granule_archive_info():
    """Test granule archive extraction handles size conversion and format safely."""
    # Happy path: Normal byte size
    size_mb, fmt = _extract_granule_archive_info(
        {
            "DataGranule": {
                "ArchiveAndDistributionInformation": [
                    {"SizeInBytes": 1048576, "Format": "NetCDF-4"}
                ]
            }
        }
    )
    assert size_mb == 1.0
    assert fmt == "NetCDF-4"

    # Missing data returns (None, None)
    assert _extract_granule_archive_info({}) == (None, None)

    # Malformed data (string instead of float) parses safely if possible
    size_mb, _ = _extract_granule_archive_info(
        {"DataGranule": {"ArchiveAndDistributionInformation": [{"SizeInBytes": "2097152"}]}}
    )
    assert size_mb == 2.0


def test_extract_granule_bounding_box():
    """Test granule MBR extraction handles floats and malformed geometry safely."""
    # Happy path: Valid coordinates
    assert _extract_granule_bounding_box(
        {
            "SpatialExtent": {
                "HorizontalSpatialDomain": {
                    "Geometry": {
                        "BoundingRectangles": [
                            {
                                "WestBoundingCoordinate": -120.0,
                                "SouthBoundingCoordinate": 30.5,
                                "EastBoundingCoordinate": -110.0,
                                "NorthBoundingCoordinate": 40.5,
                            }
                        ]
                    }
                }
            }
        }
    ) == [-120.0, 30.5, -110.0, 40.5]

    # Missing data returns None
    assert _extract_granule_bounding_box({}) is None

    # Malformed data (string instead of float array) safely ignored
    assert (
        _extract_granule_bounding_box(
            {
                "SpatialExtent": {
                    "HorizontalSpatialDomain": {
                        "Geometry": {"BoundingRectangles": ["Not a dictionary"]}
                    }
                }
            }
        )
        is None
    )

    # Malformed nested objects return None cleanly
    assert _extract_granule_bounding_box({"SpatialExtent": "Not a dict"}) is None
    assert (
        _extract_granule_bounding_box({"SpatialExtent": {"HorizontalSpatialDomain": "Not a dict"}})
        is None
    )
    assert (
        _extract_granule_bounding_box(
            {"SpatialExtent": {"HorizontalSpatialDomain": {"Geometry": "Not a dict"}}}
        )
        is None
    )
    assert (
        _extract_granule_bounding_box(
            {
                "SpatialExtent": {
                    "HorizontalSpatialDomain": {"Geometry": {"BoundingRectangles": "Not a list"}}
                }
            }
        )
        is None
    )

    # Missing keys in dictionary fail safely
    assert (
        _extract_granule_bounding_box(
            {
                "SpatialExtent": {
                    "HorizontalSpatialDomain": {
                        "Geometry": {"BoundingRectangles": [{"WestBoundingCoordinate": 1.0}]}
                    }
                }
            }
        )
        is None
    )

    # Unparseable float string in dictionary fails safely
    assert (
        _extract_granule_bounding_box(
            {
                "SpatialExtent": {
                    "HorizontalSpatialDomain": {
                        "Geometry": {
                            "BoundingRectangles": [
                                {
                                    "WestBoundingCoordinate": "invalid",
                                    "SouthBoundingCoordinate": 2.0,
                                    "EastBoundingCoordinate": 3.0,
                                    "NorthBoundingCoordinate": 4.0,
                                }
                            ]
                        }
                    }
                }
            }
        )
        is None
    )


def test_extract_missing_fields_safely():
    """Test that missing internal dictionary fields safely continue loops without error."""
    # Missing Value or Unit skips cleanly
    assert (
        _extract_collection_temporal_resolution(
            {"TemporalExtents": [{"TemporalResolutions": [{"Unit": "Day"}, {"Value": 8}]}]}
        )
        is None
    )

    # Malformed array elements (string instead of dict) skip cleanly
    assert (
        _extract_collection_temporal_resolution(
            {"TemporalExtents": ["Not a dict", {"TemporalResolutions": ["Not a dict"]}]}
        )
        is None
    )

    # Malformed resolution lists skip cleanly
    assert (
        _extract_collection_spatial_resolution(
            {
                "SpatialExtent": {
                    "HorizontalSpatialDomain": {
                        "ResolutionAndCoordinateSystem": {
                            "HorizontalDataResolution": {"GriddedResolutions": ["Not a dict", []]}
                        }
                    }
                }
            }
        )
        is None
    )

    # Malformed archive info elements skip cleanly
    assert _extract_granule_archive_info(
        {"DataGranule": {"ArchiveAndDistributionInformation": ["Not a dict"]}}
    ) == (None, None)

    # Malformed bounding boxes skip cleanly
    assert (
        _extract_granule_bounding_box(
            {
                "SpatialExtent": {
                    "HorizontalSpatialDomain": {"Geometry": {"BoundingRectangles": ["Not a dict"]}}
                }
            }
        )
        is None
    )

    # Missing unit skips cleanly
    assert (
        _extract_collection_spatial_resolution(
            {
                "SpatialExtent": {
                    "HorizontalSpatialDomain": {
                        "ResolutionAndCoordinateSystem": {
                            "HorizontalDataResolution": {
                                "GriddedResolutions": [{"XDimension": 30, "YDimension": 30}]
                            }
                        }
                    }
                }
            }
        )
        is None
    )

    # Missing size falls back to None size safely
    size_mb, fmt = _extract_granule_archive_info(
        {"DataGranule": {"ArchiveAndDistributionInformation": [{"Format": "NetCDF-4"}]}}
    )
    assert size_mb is None
    assert fmt == "NetCDF-4"

    # Guard tests for _extract_collection_temporal_resolution
    assert _extract_collection_temporal_resolution({"TemporalExtents": ["not_a_dict"]}) is None
    assert (
        _extract_collection_temporal_resolution(
            {"TemporalExtents": [{"TemporalResolutions": ["not_a_dict"]}]}
        )
        is None
    )
    assert (
        _extract_collection_temporal_resolution(
            {"TemporalExtents": [{"TemporalResolution": "not_a_dict"}]}
        )
        is None
    )

    # Guard tests for _extract_collection_spatial_resolution
    assert _extract_collection_spatial_resolution({"SpatialExtent": "not_a_dict"}) is None
    assert (
        _extract_collection_spatial_resolution(
            {"SpatialExtent": {"HorizontalSpatialDomain": "not_a_dict"}}
        )
        is None
    )
    assert (
        _extract_collection_spatial_resolution(
            {
                "SpatialExtent": {
                    "HorizontalSpatialDomain": {"ResolutionAndCoordinateSystem": "not_a_dict"}
                }
            }
        )
        is None
    )
    assert (
        _extract_collection_spatial_resolution(
            {
                "SpatialExtent": {
                    "HorizontalSpatialDomain": {
                        "ResolutionAndCoordinateSystem": {"HorizontalDataResolution": "not_a_dict"}
                    }
                }
            }
        )
        is None
    )
    assert (
        _extract_collection_spatial_resolution(
            {
                "SpatialExtent": {
                    "HorizontalSpatialDomain": {
                        "ResolutionAndCoordinateSystem": {
                            "HorizontalDataResolution": {"GriddedResolutions": "not_a_list"}
                        }
                    }
                }
            }
        )
        is None
    )
    assert (
        _extract_collection_spatial_resolution(
            {
                "SpatialExtent": {
                    "HorizontalSpatialDomain": {
                        "ResolutionAndCoordinateSystem": {
                            "HorizontalDataResolution": {"GriddedResolutions": ["not_a_dict"]}
                        }
                    }
                }
            }
        )
        is None
    )

    # Guard tests for _extract_granule_archive_info
    assert _extract_granule_archive_info({"DataGranule": "not_a_dict"}) == (None, None)
    assert _extract_granule_archive_info(
        {"DataGranule": {"ArchiveAndDistributionInformation": "not_a_list"}}
    ) == (None, None)
    assert _extract_granule_archive_info(
        {"DataGranule": {"ArchiveAndDistributionInformation": ["not_a_dict"]}}
    ) == (None, None)

    # Force ValueError in _extract_granule_archive_info
    size_mb, fmt = _extract_granule_archive_info(
        {
            "DataGranule": {
                "ArchiveAndDistributionInformation": [
                    {"SizeInBytes": "not_a_float", "Format": "HDF5"}
                ]
            }
        }
    )
    assert size_mb is None
    assert fmt == "HDF5"

    # Guard tests for _extract_granule_bounding_box
    assert _extract_granule_bounding_box({"SpatialExtent": "not_a_dict"}) is None
    assert (
        _extract_granule_bounding_box({"SpatialExtent": {"HorizontalSpatialDomain": "not_a_dict"}})
        is None
    )
    assert (
        _extract_granule_bounding_box(
            {"SpatialExtent": {"HorizontalSpatialDomain": {"Geometry": "not_a_dict"}}}
        )
        is None
    )
    assert (
        _extract_granule_bounding_box(
            {
                "SpatialExtent": {
                    "HorizontalSpatialDomain": {"Geometry": {"BoundingRectangles": "not_a_list"}}
                }
            }
        )
        is None
    )
    assert (
        _extract_granule_bounding_box(
            {
                "SpatialExtent": {
                    "HorizontalSpatialDomain": {"Geometry": {"BoundingRectangles": ["not_a_dict"]}}
                }
            }
        )
        is None
    )
