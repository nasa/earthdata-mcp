"""Tests for the get_collections MCP tool."""

import importlib
from unittest.mock import patch

from util.cmr.client import CMRError, CMRSearchResponse


def _load_tool():
    return importlib.import_module("tools.get_collections.tool")


def test_get_collections_allows_unfiltered_search(monkeypatch):
    """The tool should allow empty search criteria for broad exploration."""
    tool = _load_tool()
    page = CMRSearchResponse(items=[], total_hits=0, took_ms=5, search_after=None, page_size=0)

    captured = {}

    def fake_search_cmr(**kwargs):
        captured.update(kwargs)
        yield page

    monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)

    output = tool.get_collections()

    assert captured["search_params"] == {}
    assert output["status"] == "no_results"


def test_get_collections_allows_temporal_only_search(monkeypatch):
    """Temporal-only searches should pass validation and run against CMR."""
    tool = _load_tool()
    page = CMRSearchResponse(items=[], total_hits=0, took_ms=6, search_after=None, page_size=0)

    captured = {}

    def fake_search_cmr(**kwargs):
        captured.update(kwargs)
        yield page

    monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)

    output = tool.get_collections(
        temporal_start_date="2024-01-01T00:00:00Z",
        temporal_end_date="2024-01-31T23:59:59Z",
    )

    assert captured["search_params"]["temporal"] == "2024-01-01T00:00:00Z,2024-01-31T23:59:59Z"
    assert output["status"] == "no_results"


def test_get_collections_allows_spatial_only_search(monkeypatch):
    """Spatial-only searches should pass validation and run against CMR."""
    tool = _load_tool()
    page = CMRSearchResponse(items=[], total_hits=0, took_ms=6, search_after=None, page_size=0)

    captured = {}

    def fake_search_cmr(**kwargs):
        captured.update(kwargs)
        yield page

    monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)

    output = tool.get_collections(spatial_wkt_geometry="POINT(-75 40)")

    assert captured["method"] == "POST"
    assert output["status"] == "no_results"


def test_get_collections_returns_normalized_results(monkeypatch):
    """The tool should normalize a single page of UMM collection results."""
    tool = _load_tool()

    page = CMRSearchResponse(
        items=[
            {
                "meta": {"concept-id": "C123-PROV"},
                "umm": {
                    "ShortName": "MOD11A1",
                    "Version": "061",
                    "EntryTitle": "MODIS/Terra Land Surface Temperature Daily L3 Global 1km",
                    "Abstract": "Daily land surface temperature product.",
                    "TemporalExtents": [
                        {
                            "RangeDateTimes": [
                                {
                                    "BeginningDateTime": "2000-02-24T00:00:00Z",
                                    "EndingDateTime": "2024-12-31T23:59:59Z",
                                }
                            ]
                        }
                    ],
                    "Platforms": [
                        {
                            "ShortName": "Terra",
                            "Instruments": [{"ShortName": "MODIS"}],
                        }
                    ],
                },
            }
        ],
        total_hits=1,
        took_ms=12,
        search_after="next-token",
        page_size=1,
    )

    captured = {}

    def fake_search_cmr(**kwargs):
        captured.update(kwargs)
        yield page

    monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)

    output = tool.get_collections(
        keyword="land surface temperature",
    )

    assert captured["concept_type"] == "collection"
    assert captured["search_params"]["keyword"] == "land surface temperature"
    assert captured["page_size"] == 10
    assert captured["method"] == "GET"
    assert output["status"] == "success"
    assert output["total_hits"] == 1
    assert output["collections"][0]["concept_id"] == "C123-PROV"
    assert output["collections"][0]["short_name"] == "MOD11A1"
    assert (
        output["collections"][0]["entry_title"]
        == "MODIS/Terra Land Surface Temperature Daily L3 Global 1km"
    )
    assert output["collections"][0]["abstract"] == "Daily land surface temperature product."
    assert output["collections"][0]["platforms"] == ["Terra"]
    assert output["collections"][0]["instruments"] == ["MODIS"]


def test_get_collections_uses_post_for_spatial_search(monkeypatch):
    """Spatial collection searches should switch to POST with a shapefile payload."""
    tool = _load_tool()
    page = CMRSearchResponse(items=[], total_hits=0, took_ms=8, search_after=None, page_size=0)

    captured = {}

    def fake_search_cmr(**kwargs):
        captured.update(kwargs)
        yield page

    monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)

    output = tool.get_collections(keyword="modis", spatial_wkt_geometry="POINT(-75 40)")

    assert captured["method"] == "POST"
    assert captured["files"] is not None
    assert output["status"] == "no_results"


def test_get_collections_includes_optional_filter_params(monkeypatch):
    """Optional concept_id, short_name, and provider should map into CMR params."""
    tool = _load_tool()
    page = CMRSearchResponse(items=[], total_hits=0, took_ms=8, search_after=None, page_size=0)

    captured = {}

    def fake_search_cmr(**kwargs):
        captured.update(kwargs)
        yield page

    monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)

    output = tool.get_collections(
        concept_id="C123-PROV",
        short_name="MOD11A1",
        provider="LPDAAC_ECS",
    )

    assert captured["search_params"]["concept_id"] == "C123-PROV"
    assert captured["search_params"]["short_name"] == "MOD11A1"
    assert captured["search_params"]["provider"] == "LPDAAC_ECS"
    assert output["status"] == "no_results"


def test_get_collections_returns_error_on_cmr_failure(monkeypatch):
    """CMR failures should be converted into stable tool errors."""
    tool = _load_tool()

    def fake_search_cmr(**_kwargs):
        raise CMRError("CMR request failed")
        yield  # pragma: no cover

    monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)

    output = tool.get_collections(keyword="modis")

    assert output["status"] == "error"
    assert output["error_message"] == "CMR request failed"


def test_get_collections_returns_no_results_when_cmr_yields_nothing(monkeypatch):
    """An empty CMR iterator should map to no_results."""
    tool = _load_tool()

    def fake_search_cmr(**_kwargs):
        return
        yield  # pragma: no cover

    monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)

    output = tool.get_collections(keyword="modis")

    assert output["status"] == "no_results"


def test_get_collections_returns_error_on_unexpected_failure(monkeypatch):
    """Unexpected failures should still return a stable tool error payload."""
    tool = _load_tool()

    def fake_search_cmr(**_kwargs):
        raise RuntimeError("unexpected failure")
        yield  # pragma: no cover

    monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)

    output = tool.get_collections(keyword="modis")

    assert output["status"] == "error"
    assert (
        output["error_message"] == "An unexpected internal error occurred during collection search."
    )


def test_get_collections_returns_error_on_invalid_spatial_wkt():
    """Invalid WKT should be returned as a stable tool error payload."""
    tool = _load_tool()

    output = tool.get_collections(keyword="modis", spatial_wkt_geometry="POINT((1 2))")

    assert output["status"] == "error"
    assert "Invalid WKT geometry" in output["error_message"]


def test_get_collections_calls_trace_update(monkeypatch):
    """Tool should emit Langfuse trace updates using the shared helper."""
    tool = _load_tool()
    page = CMRSearchResponse(items=[], total_hits=0, took_ms=5, search_after=None, page_size=0)

    def fake_search_cmr(**_kwargs):
        yield page

    monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)

    with patch.object(tool, "trace_update") as mock_trace_update:
        output = tool.get_collections(keyword="modis")

    assert output["status"] == "no_results"
    assert mock_trace_update.called


# --- pagination ---


def _make_collection_item(concept_id="C1-PROV"):
    """Minimal UMM collection item for pagination/field tests."""
    return {
        "meta": {"concept-id": concept_id},
        "umm": {
            "ShortName": "SHORT",
            "EntryTitle": "A Collection Title",
            "Abstract": "Abstract text",
        },
    }


def test_get_collections_returns_next_cursor_when_page_is_full(monkeypatch):
    """next_cursor must be set when items == limit and search_after token is present."""
    tool = _load_tool()
    page = CMRSearchResponse(
        items=[_make_collection_item()],
        total_hits=5,
        took_ms=5,
        search_after="tok-abc",
        page_size=1,
    )

    monkeypatch.setattr(tool, "search_cmr", lambda **_: iter([page]))

    output = tool.get_collections(limit=1)

    assert output["next_cursor"] is not None


def test_get_collections_returns_no_cursor_on_last_page(monkeypatch):
    """next_cursor must be None when items < limit."""
    tool = _load_tool()
    page = CMRSearchResponse(
        items=[_make_collection_item()],
        total_hits=1,
        took_ms=5,
        search_after="tok-xyz",
        page_size=1,
    )

    monkeypatch.setattr(tool, "search_cmr", lambda **_: iter([page]))

    output = tool.get_collections(limit=5)

    assert output["next_cursor"] is None


def test_get_collections_cursor_passes_search_after(monkeypatch):
    """A valid CMR cursor must decode and pass search_after to the backend."""
    from util.pagination import encode_cursor

    tool = _load_tool()
    page = CMRSearchResponse(items=[], total_hits=0, took_ms=5, search_after=None, page_size=0)
    captured = {}

    def fake_search_cmr(**kwargs):
        captured.update(kwargs)
        yield page

    monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)

    cursor = encode_cursor("cmr", {"token": "some-search-after-token", "params": {}})
    tool.get_collections(cursor=cursor)

    assert captured.get("search_after") == "some-search-after-token"


def test_get_collections_passes_limit_as_page_size(monkeypatch):
    """The limit param must be forwarded to CMR as page_size."""
    tool = _load_tool()
    page = CMRSearchResponse(items=[], total_hits=0, took_ms=5, search_after=None, page_size=0)
    captured = {}

    def fake_search_cmr(**kwargs):
        captured.update(kwargs)
        yield page

    monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)

    tool.get_collections(limit=25)

    assert captured.get("page_size") == 25


def test_get_collections_returns_error_on_invalid_cursor(monkeypatch):
    """An invalid cursor string must produce a clean error response, not an exception."""
    tool = _load_tool()
    page = CMRSearchResponse(items=[], total_hits=0, took_ms=5, search_after=None, page_size=0)
    monkeypatch.setattr(tool, "search_cmr", lambda **_: iter([page]))

    output = tool.get_collections(cursor="this-is-not-a-valid-cursor!@#")

    assert output["status"] == "error"
    assert "cursor" in output["error_message"].lower()


def test_get_collections_returns_error_on_cross_backend_cursor(monkeypatch):
    """A KMS cursor passed to get_collections must produce a clean error response."""
    from util.pagination import encode_cursor

    tool = _load_tool()
    page = CMRSearchResponse(items=[], total_hits=0, took_ms=5, search_after=None, page_size=0)
    monkeypatch.setattr(tool, "search_cmr", lambda **_: iter([page]))

    kms_cursor = encode_cursor("kms", 20)
    output = tool.get_collections(cursor=kms_cursor)

    assert output["status"] == "error"
    assert "cursor" in output["error_message"].lower()


# --- field filtering ---


def test_get_collections_fields_filtering_keeps_mandatory_fields(monkeypatch):
    """fields param must keep only requested fields plus concept_id and entry_title."""
    tool = _load_tool()
    page = CMRSearchResponse(
        items=[_make_collection_item()],
        total_hits=1,
        took_ms=5,
        search_after=None,
        page_size=1,
    )
    monkeypatch.setattr(tool, "search_cmr", lambda **_: iter([page]))

    output = tool.get_collections(fields=["abstract"])

    item = output["collections"][0]
    assert "concept_id" in item
    assert "entry_title" in item
    assert "abstract" in item
    assert "short_name" not in item


def test_get_collections_fields_empty_returns_all_fields(monkeypatch):
    """When fields is empty, all normalized fields must be present."""
    tool = _load_tool()
    page = CMRSearchResponse(
        items=[_make_collection_item()],
        total_hits=1,
        took_ms=5,
        search_after=None,
        page_size=1,
    )
    monkeypatch.setattr(tool, "search_cmr", lambda **_: iter([page]))

    output = tool.get_collections(fields=[])

    item = output["collections"][0]
    assert "abstract" in item
    assert "short_name" in item


# --- new search params ---


def test_get_collections_platform_param(monkeypatch):
    """platform param must map to platform[] in CMR search_params."""
    tool = _load_tool()
    page = CMRSearchResponse(items=[], total_hits=0, took_ms=5, search_after=None, page_size=0)
    captured = {}

    def fake_search_cmr(**kwargs):
        captured.update(kwargs)
        yield page

    monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)

    tool.get_collections(platform=["Terra", "Aqua"])

    assert captured["search_params"].get("platform[]") == ["Terra", "Aqua"]


def test_get_collections_instrument_param(monkeypatch):
    """instrument param must map to instrument[] in CMR search_params."""
    tool = _load_tool()
    page = CMRSearchResponse(items=[], total_hits=0, took_ms=5, search_after=None, page_size=0)
    captured = {}

    def fake_search_cmr(**kwargs):
        captured.update(kwargs)
        yield page

    monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)

    tool.get_collections(instrument=["MODIS"])

    assert captured["search_params"].get("instrument[]") == ["MODIS"]


def test_get_collections_processing_level_id_param(monkeypatch):
    """processing_level_id param must map to processing_level_id[] in CMR search_params."""
    tool = _load_tool()
    page = CMRSearchResponse(items=[], total_hits=0, took_ms=5, search_after=None, page_size=0)
    captured = {}

    def fake_search_cmr(**kwargs):
        captured.update(kwargs)
        yield page

    monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)

    tool.get_collections(processing_level_id=["3", "3A"])

    assert captured["search_params"].get("processing_level_id[]") == ["3", "3A"]


def test_get_collections_has_granules_param(monkeypatch):
    """has_granules=True must appear in CMR search_params."""
    tool = _load_tool()
    page = CMRSearchResponse(items=[], total_hits=0, took_ms=5, search_after=None, page_size=0)
    captured = {}

    def fake_search_cmr(**kwargs):
        captured.update(kwargs)
        yield page

    monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)

    tool.get_collections(has_granules=True)

    assert captured["search_params"].get("has_granules") is True


# --- new response fields ---


def _make_rich_collection_item():
    """UMM collection item with all new Phase 2 fields populated."""
    return {
        "meta": {"concept-id": "C1-PROV"},
        "umm": {
            "ShortName": "SHORT",
            "EntryTitle": "A Collection",
            "CollectionProgress": "ACTIVE",
            "ScienceKeywords": [
                {
                    "Category": "EARTH SCIENCE",
                    "Topic": "LAND SURFACE",
                    "Term": "SURFACE THERMAL PROPERTIES",
                }
            ],
            "SpatialExtent": {
                "HorizontalSpatialDomain": {
                    "Geometry": {
                        "BoundingRectangles": [
                            {
                                "WestBoundingCoordinate": -180.0,
                                "EastBoundingCoordinate": 180.0,
                                "NorthBoundingCoordinate": 90.0,
                                "SouthBoundingCoordinate": -90.0,
                            }
                        ]
                    }
                }
            },
            "DataCenters": [{"Roles": ["ARCHIVER"], "ShortName": "PODAAC"}],
            "ArchiveAndDistributionInformation": {
                "FileDistributionInformation": [{"Format": "NetCDF-4", "Media": ["Online"]}]
            },
        },
    }


def test_get_collections_new_response_fields_present(monkeypatch):
    """science_keywords, collection_progress, bounding_box, data_centers, and
    archive_and_distribution_information must all appear in normalized output."""
    tool = _load_tool()
    page = CMRSearchResponse(
        items=[_make_rich_collection_item()],
        total_hits=1,
        took_ms=5,
        search_after=None,
        page_size=1,
    )
    monkeypatch.setattr(tool, "search_cmr", lambda **_: iter([page]))

    output = tool.get_collections()

    item = output["collections"][0]
    assert "science_keywords" in item
    assert item["science_keywords"][0]["Category"] == "EARTH SCIENCE"
    assert "collection_progress" in item
    assert item["collection_progress"] == "ACTIVE"
    assert "bounding_box" in item
    assert item["bounding_box"] == [-180.0, -90.0, 180.0, 90.0]
    assert "data_centers" in item
    assert item["data_centers"][0]["short_name"] == "PODAAC"
    assert "archive_and_distribution_information" in item
    assert item["archive_and_distribution_information"][0]["format"] == "NetCDF-4"


def test_get_collections_old_format_cursor_returns_error(monkeypatch):
    """An old-format (scalar value) cursor must return a clean error."""
    from util.pagination import encode_cursor

    tool = _load_tool()
    page = CMRSearchResponse(items=[], total_hits=0, took_ms=5, search_after=None, page_size=0)
    monkeypatch.setattr(tool, "search_cmr", lambda **_: iter([page]))

    old_cursor = encode_cursor("cmr", "some-legacy-token")
    output = tool.get_collections(cursor=old_cursor)

    assert output["status"] == "error"
    assert "outdated" in output["error_message"].lower()


def test_get_collections_cursor_override():
    from tools.get_collections.tool import get_collections
    from util.pagination import encode_cursor

    cursor = encode_cursor("cmr", {"token": "tok-abc", "params": {"keyword": "original"}})
    res = get_collections(keyword="changed", cursor=cursor)
    assert res["status"] == "error"
    assert "query-scoped" in res["error_message"]


def test_get_collections_validation_error():
    from tools.get_collections.tool import get_collections

    res = get_collections(keyword="", limit=100)
    assert res["status"] == "error"


def test_get_collections_wkt_error():
    from tools.get_collections.tool import get_collections

    res = get_collections(spatial_wkt_geometry="INVALID WKT")
    assert res["status"] == "error"
    assert "Invalid WKT" in res["error_message"]


def test_get_collections_cursor_post():
    from unittest.mock import patch

    from tools.get_collections.tool import get_collections
    from util.pagination import encode_cursor

    c = encode_cursor("cmr", {"token": "x", "spatial": "POINT(0 0)", "params": {}})
    with patch("tools.get_collections.tool.search_cmr") as mock_search:
        get_collections(cursor=c, spatial_wkt_geometry="POINT(0 0)")
        mock_search.assert_called_once()


def test_get_collections_safe_exception_surfacing(monkeypatch):
    from tools.get_collections.tool import get_collections

    def fake_search_value_error(*args, **kwargs):
        raise ValueError("Safe validation error")

    monkeypatch.setattr("tools.get_collections.tool.search_cmr", fake_search_value_error)
    output = get_collections(keyword="modis")
    assert output["status"] == "error"
    assert "Safe validation error" in output["error_message"]

    def fake_search_generic_error(*args, **kwargs):
        raise Exception("Fake secret")

    monkeypatch.setattr("tools.get_collections.tool.search_cmr", fake_search_generic_error)
    output = get_collections(keyword="modis")
    assert output["status"] == "error"
    assert "Fake secret" not in output["error_message"]
    assert "unexpected internal error" in output["error_message"].lower()
