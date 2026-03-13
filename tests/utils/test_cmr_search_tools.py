"""Tests for util.cmr.search_tools helpers."""

from datetime import UTC, datetime

import pytest

from util.cmr.search_tools import (
    _count_geometry_points,
    _dedupe_strings,
    build_spatial_files,
    extract_access_urls,
    extract_granule_temporal_extent,
    format_temporal_range,
    normalize_collection_item,
    normalize_granule_item,
)


def test_build_spatial_files_raises_value_error_for_invalid_wkt():
    """Malformed WKT should be normalized to ValueError."""
    with pytest.raises(ValueError, match="Invalid WKT geometry"):
        build_spatial_files("POINT((1 2))")


def test_format_temporal_range_returns_none_when_bounds_missing():
    assert format_temporal_range(None, None) is None


def test_format_temporal_range_accepts_datetimes_and_strings():
    start = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
    end = "2024-01-31T23:59:59Z"

    assert format_temporal_range(start, end) == "2024-01-01T00:00:00Z,2024-01-31T23:59:59Z"


def test_format_temporal_range_handles_open_start_bound():
    assert format_temporal_range(None, "2024-01-31T23:59:59Z") == ",2024-01-31T23:59:59Z"


def test_format_temporal_range_rejects_invalid_type():
    with pytest.raises(ValueError, match="temporal_start_date"):
        format_temporal_range(123, None)


def test_format_temporal_range_rejects_invalid_iso_string():
    with pytest.raises(ValueError, match="temporal_end_date"):
        format_temporal_range(None, "not-an-iso-time")


def test_build_spatial_files_returns_none_for_empty_input():
    assert build_spatial_files(None) is None


def test_build_spatial_files_rejects_too_many_points():
    # 5001 coordinates exceeds CMR's 5000-point upload limit.
    coords = ", ".join(f"{i} 0" for i in range(5001))
    with pytest.raises(ValueError, match="exceeding the CMR shapefile limit"):
        build_spatial_files(f"LINESTRING({coords})")


def test_build_spatial_files_repairs_invalid_geometry():
    files = build_spatial_files("POLYGON((0 0, 2 2, 2 0, 0 2, 0 0))")

    assert files is not None
    assert "shapefile" in files


def test_build_spatial_files_rejects_payload_over_limit(monkeypatch):
    monkeypatch.setattr("util.cmr.search_tools._CMR_MAX_BYTES", 10)

    with pytest.raises(ValueError, match="exceeding the CMR limit"):
        build_spatial_files("POINT(1 2)")


def test_count_geometry_points_polygon_and_multi_polygon():
    polygon_file = build_spatial_files("POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))")
    multi_file = build_spatial_files(
        "MULTIPOLYGON(((0 0, 1 0, 1 1, 0 1, 0 0)),((2 2, 3 2, 3 3, 2 3, 2 2)))"
    )

    assert polygon_file is not None
    assert multi_file is not None


def test_count_geometry_points_returns_zero_for_unknown_geom_type():
    class UnknownGeometry:
        geom_type = "Unknown"

    assert _count_geometry_points(UnknownGeometry()) == 0


def test_extract_granule_temporal_extent_supports_range_date_times():
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
    normalized = normalize_collection_item(
        {"meta": {"concept-id": "C1"}, "umm": {"ShortName": "SN"}}
    )

    assert normalized["concept_id"] == "C1"
    assert normalized["title"] == "SN"
    assert normalized["version"] is None
    assert normalized["platforms"] == []
    assert normalized["instruments"] == []


def test_normalize_granule_item_falls_back_to_umm_collection_concept_id():
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
    assert _dedupe_strings(["a", "", "b", "a", "b", "c"]) == ["a", "b", "c"]
