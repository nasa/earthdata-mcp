"""Tests for util.cmr.search_tools."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from shapely.geometry import LineString, MultiPoint, Point, Polygon

from util.cmr.search_tools import (
    _coerce_temporal_input,
    _count_geometry_points,
    _dedupe_strings,
    _extract_collection_archive_info,
    _extract_collection_data_centers,
    _extract_collection_spatial_resolution,
    _extract_collection_temporal_resolution,
    _extract_granule_additional_attributes,
    _extract_granule_archive_info,
    _extract_granule_bounding_box,
    _extract_granule_orbit_info,
    _normalize_geometry_for_cmr,
    build_spatial_files,
    extract_access_urls,
    extract_granule_temporal_extent,
    fetch_association_ids,
    format_cloud_cover_range,
    format_temporal_range,
    normalize_citation_item,
    normalize_collection_item,
    normalize_granule_item,
    normalize_service_item,
    normalize_tool_item,
    normalize_variable_item,
)


def test_format_cloud_cover_range():
    """Test function."""
    assert format_cloud_cover_range(None, None) is None
    assert format_cloud_cover_range(10.5, 20.0) == "10.5,20"
    assert format_cloud_cover_range(None, 20.0) == ",20"
    assert format_cloud_cover_range(10.0, None) == "10,"


def test_coerce_temporal_input():
    """Test function."""
    assert _coerce_temporal_input(None, "test") is None
    dt = datetime(2020, 1, 1, tzinfo=UTC)
    assert _coerce_temporal_input(dt, "test") == dt
    assert _coerce_temporal_input("2020-01-01T00:00:00Z", "test") == dt
    with pytest.raises(ValueError):
        _coerce_temporal_input("invalid", "test")
    with pytest.raises(ValueError):
        _coerce_temporal_input(123, "test")


def test_format_temporal_range():
    """Test function."""
    assert format_temporal_range(None, None) is None
    dt = datetime(2020, 1, 1, tzinfo=UTC)
    res = format_temporal_range(dt, None)
    assert res == "2020-01-01T00:00:00Z,"
    res2 = format_temporal_range(None, "2020-01-01T00:00:00Z")
    assert res2 == ",2020-01-01T00:00:00Z"


def test_count_geometry_points():
    """Test function."""
    assert _count_geometry_points(Point(0, 0)) == 1
    assert _count_geometry_points(LineString([(0, 0), (1, 1)])) == 2
    assert _count_geometry_points(Polygon([(0, 0), (1, 0), (1, 1), (0, 0)])) == 4
    assert _count_geometry_points(MultiPoint([(0, 0), (1, 1)])) == 2
    # Something else
    assert _count_geometry_points(MagicMock(geom_type="Unknown")) == 0


def test_normalize_geometry_for_cmr():
    """Test function."""
    p = Point(0, 0)
    assert _normalize_geometry_for_cmr(p) == p
    poly = Polygon([(0, 0), (1, 1), (1, 0), (0, 0)])  # invalid winding maybe
    # orient_polygons called for Polygon
    res = _normalize_geometry_for_cmr(poly)
    assert res.geom_type == "Polygon"


def test_build_spatial_files():
    """Test function."""
    assert build_spatial_files(None) is None

    # invalid WKT
    with pytest.raises(ValueError, match="Invalid WKT"):
        build_spatial_files("INVALID")

    res = build_spatial_files("POINT(0 0)")
    assert "shapefile" in res

    # Exceed limits
    pts = ",".join(f"{i} {i}" for i in range(5001))
    with pytest.raises(ValueError, match="exceeding the CMR shapefile limit"):
        build_spatial_files(f"LINESTRING({pts})")

    # max bytes
    with (
        patch("util.cmr.search_tools._CMR_MAX_BYTES", 10),
        pytest.raises(ValueError, match="exceeding the CMR limit of"),
    ):
        build_spatial_files("POINT(0 0)")


def test_normalize_collection_item():
    """Test function."""
    item = {
        "meta": {"concept-id": "C1", "native-id": "N1"},
        "umm": {
            "ShortName": "SN",
            "Version": 1,
            "Platforms": [{"ShortName": "P1", "Instruments": [{"ShortName": "I1"}]}],
            "RelatedUrls": [{"URL": "http", "Type": "T"}],
            "ProcessingLevel": {"Id": "L1"},
            "DOI": {"DOI": "doi"},
        },
    }
    with patch("util.cmr.search_tools.extract_temporal_extent", return_value=(None, None, False)):
        res = normalize_collection_item(item)
        assert res["concept_id"] == "C1"
        assert res["version"] == "1"
        assert res["platforms"] == ["P1"]
        assert res["instruments"] == ["I1"]
        assert res["processing_level_id"] == "L1"
        assert res["doi"] == "doi"
        assert res["related_urls"][0]["url"] == "http"


def test_extract_granule_temporal_extent():
    """Test function."""
    assert extract_granule_temporal_extent({}) == (None, None)

    umm = {"TemporalExtent": {"RangeDateTime": {"BeginningDateTime": "2020-01-01T00:00:00Z"}}}
    s, e = extract_granule_temporal_extent(umm)
    assert s is not None
    assert e is None

    umm2 = {"TemporalExtent": {"RangeDateTimes": [{"BeginningDateTime": "2020-01-01T00:00:00Z"}]}}
    s2, _ = extract_granule_temporal_extent(umm2)
    assert s2 is not None


def test_normalize_granule_item():
    """Test function."""
    item = {
        "meta": {"concept-id": "G1"},
        "umm": {"CollectionConceptId": "C1", "DataGranule": {"DayNightFlag": "Day"}},
    }
    with (
        patch("util.cmr.search_tools.extract_granule_temporal_extent", return_value=(None, None)),
        patch("util.cmr.search_tools._extract_granule_archive_info", return_value=(1.0, "HDF")),
    ):
        res = normalize_granule_item(item)
        assert res["concept_id"] == "G1"
        assert res["collection_concept_id"] == "C1"
        assert res["size_mb"] == 1.0
        assert res["day_night_flag"] == "Day"


def test_extract_access_urls():
    """Test function."""
    umm = {
        "OnlineAccessURLs": ["url1", {"URL": "url2"}],
        "RelatedUrls": [{"URL": "url3", "URLContentType": "DistributionURL"}],
    }
    res = extract_access_urls(umm)
    assert res == ["url1", "url2", "url3"]


def test_normalize_tool_item():
    """Test function."""
    item = {"meta": {"concept-id": "T1"}, "umm": {"Name": "Tool1"}}
    res = normalize_tool_item(item)
    assert res["name"] == "Tool1"


def test_normalize_service_item():
    """Test function."""
    item = {
        "meta": {"concept-id": "S1"},
        "umm": {"Name": "Svc1", "ServiceOrganizations": [{"Roles": ["r"], "ShortName": "sn"}]},
    }
    res = normalize_service_item(item)
    assert res["service_organizations"][0]["short_name"] == "sn"


def test_extract_granule_orbit_info():
    """Test function."""
    assert _extract_granule_orbit_info({}) == []
    umm = {"OrbitCalculatedSpatialDomains": [{"OrbitNumber": 1}]}
    assert _extract_granule_orbit_info(umm)[0]["orbit_number"] == 1


def test_extract_granule_additional_attributes():
    """Test function."""
    assert _extract_granule_additional_attributes({}) == []
    umm = {"AdditionalAttributes": [{"Name": "A", "Values": ["1"]}]}
    assert _extract_granule_additional_attributes(umm)[0]["name"] == "A"


def test_extract_collection_data_centers():
    """Test function."""
    assert _extract_collection_data_centers({}) == []
    umm = {"DataCenters": [{"Roles": ["ARCHIVER"], "ShortName": "DC1"}]}
    res = _extract_collection_data_centers(umm)
    assert res[0]["role"] == "ARCHIVER"


def test_extract_collection_archive_info():
    """Test function."""
    assert _extract_collection_archive_info({}) == []
    umm = {
        "ArchiveAndDistributionInformation": {
            "FileDistributionInformation": [{"Format": "HDF", "Media": ["Online"]}]
        }
    }
    res = _extract_collection_archive_info(umm)
    assert res[0]["format"] == "HDF"
    assert res[0]["media_type"] == "Online"


def test_dedupe_strings():
    """Test function."""
    assert _dedupe_strings(["a", "b", "a", "", None]) == ["a", "b"]


def test_extract_collection_temporal_resolution():
    """Test function."""
    assert _extract_collection_temporal_resolution({}) is None
    umm = {"TemporalExtents": [{"TemporalResolutions": [{"Value": "1", "Unit": "Day"}]}]}
    assert _extract_collection_temporal_resolution(umm) == "1 Day"
    umm2 = {"TemporalExtents": [{"TemporalResolution": {"Value": "1", "Unit": "Month"}}]}
    assert _extract_collection_temporal_resolution(umm2) == "1 Month"


def test_extract_collection_spatial_resolution():
    """Test function."""
    assert _extract_collection_spatial_resolution({}) is None
    umm = {
        "SpatialExtent": {
            "HorizontalSpatialDomain": {
                "ResolutionAndCoordinateSystem": {
                    "HorizontalDataResolution": {
                        "GriddedResolutions": [
                            {"XDimension": 10, "YDimension": 10, "Unit": "Meters"}
                        ]
                    }
                }
            }
        }
    }
    assert _extract_collection_spatial_resolution(umm) == "10x10 Meters"

    umm2 = {
        "SpatialExtent": {
            "HorizontalSpatialDomain": {
                "ResolutionAndCoordinateSystem": {
                    "HorizontalDataResolution": {
                        "GriddedResolutions": [{"XDimension": 10, "Unit": "Meters"}]
                    }
                }
            }
        }
    }
    assert _extract_collection_spatial_resolution(umm2) == "10 Meters"


def test_extract_granule_archive_info():
    """Test function."""
    assert _extract_granule_archive_info({}) == (None, None)
    umm = {
        "DataGranule": {
            "ArchiveAndDistributionInformation": [{"SizeInBytes": 1048576, "Format": "HDF"}]
        }
    }
    s, f = _extract_granule_archive_info(umm)
    assert s == 1.0
    assert f == "HDF"


def test_extract_granule_bounding_box():
    """Test function."""
    assert _extract_granule_bounding_box({}) is None
    umm = {
        "SpatialExtent": {
            "HorizontalSpatialDomain": {
                "Geometry": {
                    "BoundingRectangles": [
                        {
                            "WestBoundingCoordinate": -10,
                            "SouthBoundingCoordinate": -10,
                            "EastBoundingCoordinate": 10,
                            "NorthBoundingCoordinate": 10,
                        }
                    ]
                }
            }
        }
    }
    assert _extract_granule_bounding_box(umm) == [-10.0, -10.0, 10.0, 10.0]


def test_normalize_citation_item():
    """Test function."""
    item = {"meta": {"concept-id": "C1"}, "umm": {"Name": "Cit"}}
    assert normalize_citation_item(item)["name"] == "Cit"


def test_normalize_variable_item():
    """Test function."""
    item = {"meta": {"concept-id": "V1"}, "umm": {"Name": "Var"}}
    assert normalize_variable_item(item)["name"] == "Var"


def test_fetch_association_ids():
    """Test function."""
    with patch("util.cmr.search_tools.search_cmr") as mock_search:
        mock_page = MagicMock()
        mock_page.items = [{"meta": {"associations": {"vars": ["V1"]}}}]
        mock_search.return_value = iter([mock_page])

        assert fetch_association_ids("C1", "vars") == ["V1"]


def test_fetch_association_ids_none():
    """Test function."""
    with patch("util.cmr.search_tools.search_cmr") as mock_search:
        mock_search.return_value = iter([])
        assert fetch_association_ids("C1", "vars") is None


def test_normalize_collection_item_invalid_types():
    """Test function."""
    item = {
        "meta": {"concept-id": "C1"},
        "umm": {
            "ProcessingLevel": "L1",  # Not dict
            "DOI": "doi",  # Not dict
            "ScienceKeywords": "invalid",
            "RelatedUrls": "invalid",
            "Platforms": {"invalid": "dict"},
            "Projects": "invalid",
        },
    }
    with patch("util.cmr.search_tools.extract_temporal_extent", return_value=(None, None, False)):
        res = normalize_collection_item(item)
        assert res["processing_level_id"] is None
        assert res["doi"] is None
        assert res["related_urls"] == []
        assert res["platforms"] == []


def test_normalize_granule_item_invalid_types():
    """Test function."""
    item = {
        "meta": {"concept-id": "G1"},
        "umm": {
            "DataGranule": "invalid",  # not dict
            "ParentCollection": "invalid",
            "RelatedUrls": "invalid",
        },
    }
    with (
        patch("util.cmr.search_tools.extract_granule_temporal_extent", return_value=(None, None)),
        patch("util.cmr.search_tools._extract_granule_archive_info", return_value=(None, None)),
    ):
        res = normalize_granule_item(item)
        assert res["day_night_flag"] is None
        assert res["production_date"] is None
        assert res["access_urls"] == []


def test_extract_access_urls_invalid_types():
    """Test function."""
    umm = {
        "OnlineAccessURLs": [123, {"URL": None}],
        "RelatedUrls": ["invalid", {"Type": "GET DATA"}],
    }
    res = extract_access_urls(umm)
    assert res == []


def test_extract_granule_orbit_info_invalid():
    """Test function."""
    assert _extract_granule_orbit_info({"OrbitCalculatedSpatialDomains": "invalid"}) == []
    assert _extract_granule_orbit_info({"OrbitCalculatedSpatialDomains": ["invalid"]}) == []


def test_extract_granule_additional_attributes_invalid():
    """Test function."""
    assert _extract_granule_additional_attributes({"AdditionalAttributes": "invalid"}) == []
    assert _extract_granule_additional_attributes({"AdditionalAttributes": ["invalid"]}) == []


def test_extract_collection_data_centers_invalid():
    """Test function."""
    assert _extract_collection_data_centers({"DataCenters": "invalid"}) == []
    assert _extract_collection_data_centers({"DataCenters": ["invalid"]}) == []


def test_extract_collection_archive_info_invalid():
    """Test function."""
    assert _extract_collection_archive_info({"ArchiveAndDistributionInformation": "invalid"}) == []
    assert (
        _extract_collection_archive_info(
            {"ArchiveAndDistributionInformation": {"FileDistributionInformation": "invalid"}}
        )
        == []
    )
    assert (
        _extract_collection_archive_info(
            {"ArchiveAndDistributionInformation": {"FileDistributionInformation": ["invalid"]}}
        )
        == []
    )


def test_extract_collection_temporal_resolution_invalid():
    """Test function."""
    assert _extract_collection_temporal_resolution({"TemporalExtents": "invalid"}) is None
    assert _extract_collection_temporal_resolution({"TemporalExtents": ["invalid"]}) is None
    assert (
        _extract_collection_temporal_resolution(
            {"TemporalExtents": [{"TemporalResolutions": "invalid"}]}
        )
        is None
    )
    assert (
        _extract_collection_temporal_resolution(
            {"TemporalExtents": [{"TemporalResolutions": ["invalid"]}]}
        )
        is None
    )


def test_extract_collection_spatial_resolution_invalid():
    """Test function."""
    assert _extract_collection_spatial_resolution({"SpatialExtent": "invalid"}) is None
    assert (
        _extract_collection_spatial_resolution(
            {"SpatialExtent": {"HorizontalSpatialDomain": "invalid"}}
        )
        is None
    )
    assert (
        _extract_collection_spatial_resolution(
            {
                "SpatialExtent": {
                    "HorizontalSpatialDomain": {"ResolutionAndCoordinateSystem": "invalid"}
                }
            }
        )
        is None
    )

    umm = {
        "SpatialExtent": {
            "HorizontalSpatialDomain": {
                "ResolutionAndCoordinateSystem": {
                    "HorizontalDataResolution": {"GriddedResolutions": "invalid"}
                }
            }
        }
    }
    assert _extract_collection_spatial_resolution(umm) is None

    umm2 = {
        "SpatialExtent": {
            "HorizontalSpatialDomain": {
                "ResolutionAndCoordinateSystem": {
                    "HorizontalDataResolution": {"GriddedResolutions": ["invalid"]}
                }
            }
        }
    }
    assert _extract_collection_spatial_resolution(umm2) is None


def test_extract_granule_archive_info_invalid():
    """Test function."""
    assert _extract_granule_archive_info({"DataGranule": "invalid"}) == (None, None)
    assert _extract_granule_archive_info(
        {"DataGranule": {"ArchiveAndDistributionInformation": "invalid"}}
    ) == (None, None)
    assert _extract_granule_archive_info(
        {"DataGranule": {"ArchiveAndDistributionInformation": ["invalid"]}}
    ) == (None, None)
    assert _extract_granule_archive_info(
        {"DataGranule": {"ArchiveAndDistributionInformation": [{"SizeInBytes": "invalid_string"}]}}
    ) == (None, None)


def test_extract_granule_bounding_box_invalid():
    """Test function."""
    assert _extract_granule_bounding_box({"SpatialExtent": "invalid"}) is None
    assert (
        _extract_granule_bounding_box({"SpatialExtent": {"HorizontalSpatialDomain": "invalid"}})
        is None
    )
    assert (
        _extract_granule_bounding_box(
            {"SpatialExtent": {"HorizontalSpatialDomain": {"Geometry": "invalid"}}}
        )
        is None
    )
    assert (
        _extract_granule_bounding_box(
            {
                "SpatialExtent": {
                    "HorizontalSpatialDomain": {"Geometry": {"BoundingRectangles": "invalid"}}
                }
            }
        )
        is None
    )
    assert (
        _extract_granule_bounding_box(
            {
                "SpatialExtent": {
                    "HorizontalSpatialDomain": {"Geometry": {"BoundingRectangles": ["invalid"]}}
                }
            }
        )
        is None
    )
    assert (
        _extract_granule_bounding_box(
            {
                "SpatialExtent": {
                    "HorizontalSpatialDomain": {
                        "Geometry": {"BoundingRectangles": [{"WestBoundingCoordinate": "invalid"}]}
                    }
                }
            }
        )
        is None
    )


def test_normalize_service_item_invalid():
    """Test function."""
    item = {"umm": {"ServiceOrganizations": ["invalid"]}}
    res = normalize_service_item(item)
    assert res["service_organizations"] == []


def test_count_geometry_points_geometry_collection():
    """Test function."""
    from shapely.geometry import GeometryCollection

    gc = GeometryCollection([Point(0, 0), LineString([(0, 0), (1, 1)])])
    assert _count_geometry_points(gc) == 3


def test_normalize_collection_item_missing_parent_coll():
    """Test function."""
    item = {"meta": {"concept-id": "G1", "parent-collection-id": "P1"}, "umm": {}}
    res = normalize_granule_item(item)
    assert res["collection_concept_id"] == "P1"


def test_extract_collection_spatial_resolution_list():
    """Test function."""
    umm = {
        "SpatialExtent": {
            "HorizontalSpatialDomain": {
                "ResolutionAndCoordinateSystem": {
                    "HorizontalDataResolution": {
                        "GriddedResolutions": [[{"XDimension": 10, "Unit": "Meters"}]]
                    }
                }
            }
        }
    }
    assert _extract_collection_spatial_resolution(umm) is None


def test_normalize_item_fuzzing():
    """Test fuzzing list extractions."""
    item_platforms_dict = {"meta": {"concept-id": "C1"}, "umm": {"Platforms": {"invalid": "dict"}}}
    with patch("util.cmr.search_tools.extract_temporal_extent", return_value=(None, None, False)):
        res = normalize_collection_item(item_platforms_dict)
        assert res["platforms"] == []

    item_instruments_dict = {
        "meta": {"concept-id": "C1"},
        "umm": {"Platforms": [{"ShortName": "P1", "Instruments": {"invalid": "dict"}}]},
    }
    with patch("util.cmr.search_tools.extract_temporal_extent", return_value=(None, None, False)):
        res = normalize_collection_item(item_instruments_dict)
        assert res["instruments"] == []

    item_urls_string = {
        "meta": {"concept-id": "G1"},
        "umm": {"OnlineAccessURLs": "string", "DataGranule": {}},
    }
    with (
        patch("util.cmr.search_tools.extract_granule_temporal_extent", return_value=(None, None)),
        patch("util.cmr.search_tools._extract_granule_archive_info", return_value=(None, None)),
    ):
        res = normalize_granule_item(item_urls_string)
        assert res["access_urls"] == []

    item_related_string = {"meta": {"concept-id": "C1"}, "umm": {"RelatedUrls": "string"}}
    with patch("util.cmr.search_tools.extract_temporal_extent", return_value=(None, None, False)):
        res = normalize_collection_item(item_related_string)
        assert res["related_urls"] == []

    item_science_keywords_string = {
        "meta": {"concept-id": "C1"},
        "umm": {"ScienceKeywords": "string"},
    }
    with patch("util.cmr.search_tools.extract_temporal_extent", return_value=(None, None, False)):
        res = normalize_collection_item(item_science_keywords_string)
        assert res["science_keywords"] == []

    item_range_date_times_string = {
        "meta": {"concept-id": "G1"},
        "umm": {"TemporalExtent": {"RangeDateTimes": "string"}, "DataGranule": {}},
    }
    with (
        patch("util.cmr.search_tools.extract_granule_temporal_extent", return_value=(None, None)),
        patch("util.cmr.search_tools._extract_granule_archive_info", return_value=(None, None)),
    ):
        res = normalize_granule_item(item_range_date_times_string)
        assert res["time_start"] is None
