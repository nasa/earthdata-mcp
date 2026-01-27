"""Tests for resolution_parsing utilities."""

from datetime import UTC, datetime

from tools.discover_data.utils import resolution_parsing


def test_parse_temporal_resolution_prefers_temporal_extents_numeric():
    umm = {
        "TemporalExtents": [
            {"TemporalResolution": {"Unit": "Day", "Value": 8}},
        ]
    }

    res_str, res_days = resolution_parsing.parse_temporal_resolution(umm)

    assert res_str == "8 Day"
    assert res_days == 8


def test_parse_temporal_resolution_handles_constant_and_varies():
    for unit in ("Constant", "Varies"):
        umm = {"TemporalExtents": [{"TemporalResolution": {"Unit": unit}}]}
        res_str, res_days = resolution_parsing.parse_temporal_resolution(umm)
        assert res_str == unit
        assert res_days is None


def test_parse_temporal_resolution_falls_back_to_title():
    umm = {"EntryTitle": "Daily Snow Cover"}

    res_str, res_days = resolution_parsing.parse_temporal_resolution(umm)

    assert res_str.lower() == "daily"
    assert res_days == 1


def test_parse_temporal_resolution_none_when_missing():
    res_str, res_days = resolution_parsing.parse_temporal_resolution({})
    assert res_str is None
    assert res_days is None


def test_parse_spatial_resolution_prefers_gridded_resolution():
    umm = {
        "SpatialExtent": {
            "HorizontalSpatialDomain": {
                "ResolutionAndCoordinateSystem": {
                    "HorizontalDataResolution": {
                        "GriddedResolutions": [
                            {"XDimension": 1.0, "Unit": "km"},
                        ]
                    }
                }
            }
        }
    }

    res_str, res_m = resolution_parsing.parse_spatial_resolution(umm)

    assert res_str == "1.0 km"
    assert res_m == 1000


def test_parse_spatial_resolution_prefers_non_gridded_when_present():
    umm = {
        "SpatialExtent": {
            "HorizontalSpatialDomain": {
                "ResolutionAndCoordinateSystem": {
                    "HorizontalDataResolution": {
                        "NonGriddedResolutions": [
                            {"XDimension": 250, "Unit": "m"},
                        ]
                    }
                }
            }
        }
    }

    res_str, res_m = resolution_parsing.parse_spatial_resolution(umm)

    assert res_str == "250 m"
    assert res_m == 250


def test_parse_spatial_resolution_handles_varies_and_point():
    for key in ("VariesResolution", "PointResolution"):
        umm = {
            "SpatialExtent": {
                "HorizontalSpatialDomain": {
                    "ResolutionAndCoordinateSystem": {
                        "HorizontalDataResolution": {key: True}
                    }
                }
            }
        }
        res_str, res_m = resolution_parsing.parse_spatial_resolution(umm)
        expected = "Varies" if key == "VariesResolution" else "Point"
        assert res_str == expected
        assert res_m is None


def test_parse_spatial_resolution_falls_back_to_title():
    umm = {"EntryTitle": "MODIS 0.25 degree"}

    res_str, res_m = resolution_parsing.parse_spatial_resolution(umm)

    assert res_str.lower().startswith("0.25")
    assert res_m == 0.25 * 111000


def test_parse_spatial_resolution_none_when_missing():
    res_str, res_m = resolution_parsing.parse_spatial_resolution({})
    assert res_str is None
    assert res_m is None


def test_parse_temporal_coverage_handles_start_end_and_ongoing():
    umm = {
        "TemporalExtents": [
            {
                "EndsAtPresentFlag": True,
                "RangeDateTimes": [
                    {"BeginningDateTime": "2020-01-01T00:00:00Z", "EndingDateTime": "2024-01-01T00:00:00Z"},
                    {"BeginningDateTime": "2019-06-01T00:00:00Z"},
                ],
            }
        ]
    }

    coverage = resolution_parsing.parse_temporal_coverage(umm)

    assert coverage.start_date == datetime(2019, 6, 1, tzinfo=UTC)
    assert coverage.end_date == datetime(2024, 1, 1, tzinfo=UTC)
    assert coverage.is_ongoing is True


def test_parse_temporal_coverage_ignores_invalid_dates():
    umm = {
        "TemporalExtents": [
            {
                "RangeDateTimes": [
                    {"BeginningDateTime": "not-a-date", "EndingDateTime": "also-bad"},
                ],
            }
        ]
    }

    coverage = resolution_parsing.parse_temporal_coverage(umm)

    assert coverage.start_date is None
    assert coverage.end_date is None
    assert coverage.is_ongoing is True


def test_parse_resolution_info_combines_temporal_and_spatial():
    umm = {
        "TemporalExtents": [{"TemporalResolution": {"Unit": "Day", "Value": 16}}],
        "SpatialExtent": {
            "HorizontalSpatialDomain": {
                "ResolutionAndCoordinateSystem": {
                    "HorizontalDataResolution": {
                        "GriddedResolutions": [
                            {"XDimension": 500, "Unit": "m"},
                        ]
                    }
                }
            }
        },
    }

    info = resolution_parsing.parse_resolution_info(umm)

    assert info.temporal_resolution == "16 Day"
    assert info.temporal_resolution_value == 16
    assert info.spatial_resolution == "500 m"
    assert info.spatial_resolution_value == 500


def test_extract_platforms_and_instruments():
    umm = {
        "Platforms": [
            {
                "ShortName": "Terra",
                "Instruments": [
                    {"ShortName": "MODIS"},
                    {"ShortName": "CERES"},
                ],
            },
            {
                "ShortName": "Aqua",
                "Instruments": [
                    {"ShortName": "MODIS"},
                ],
            },
        ]
    }

    platforms = resolution_parsing.extract_platforms(umm)
    instruments = resolution_parsing.extract_instruments(umm)

    assert platforms == ["Terra", "Aqua"]
    assert set(instruments) == {"MODIS", "CERES"}


def test_normalize_temporal_to_days_handles_units():
    fn = resolution_parsing._normalize_temporal_to_days  # type: ignore[attr-defined]
    assert fn(12, "hour") == 0.5
    assert fn(2, "week") == 14
    assert fn(1, "year") == 365
    assert fn(1, "minute") == 1 / 1440
    assert fn(1, "unknown") is None


def test_normalize_temporal_from_text_parses_patterns():
    fn = resolution_parsing._normalize_temporal_from_text  # type: ignore[attr-defined]
    assert fn("Daily product") == 1
    assert fn("8-day composite") == 8
    assert fn("Hourly data") == 1 / 24
    assert fn("No resolution") is None


def test_normalize_spatial_to_meters_conversions():
    fn = resolution_parsing._normalize_spatial_to_meters  # type: ignore[attr-defined]
    assert fn(1, "m") == 1
    assert fn(2, "km") == 2000
    assert fn(0.25, "degree") == 0.25 * 111000
    assert fn(3, "arc-sec") == 90
    assert fn(1, "nautical mile") == 1852
    assert fn(1, "mile") == 1609
    assert fn(1, "unknown") is None


def test_normalize_spatial_from_text_patterns():
    fn = resolution_parsing._normalize_spatial_from_text  # type: ignore[attr-defined]
    assert fn("500 m product") == 500
    assert fn("1.5 km") == 1500
    assert fn("0.5 deg") == 0.5 * 111000
    assert fn("no match") is None
