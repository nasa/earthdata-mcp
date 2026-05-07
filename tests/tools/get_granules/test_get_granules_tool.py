"""Tests for the get_granules MCP tool."""

import importlib
from unittest.mock import patch

from util.cmr.client import CMRError, CMRSearchResponse


def _load_tool():
    return importlib.import_module("tools.get_granules.tool")


def test_get_granules_returns_normalized_results(monkeypatch):
    """The tool should normalize a single page of UMM granule results."""
    tool = _load_tool()

    page = CMRSearchResponse(
        items=[
            {
                "meta": {
                    "concept-id": "G123-PROV",
                    "parent-collection-id": "C123-PROV",
                },
                "umm": {
                    "GranuleUR": "MOD11A1.A2024001.h00v08.061",
                    "ProducerGranuleId": "MOD11A1.A2024001.h00v08.061.hdf",
                    "TemporalExtent": {
                        "RangeDateTime": {
                            "BeginningDateTime": "2024-01-01T00:00:00Z",
                            "EndingDateTime": "2024-01-01T23:59:59Z",
                        }
                    },
                    "OnlineAccessURLs": [{"URL": "https://example.com/data.hdf"}],
                    "RelatedUrls": [
                        {
                            "URLContentType": "DistributionURL",
                            "Type": "GET DATA",
                            "URL": "https://example.com/download.hdf",
                        }
                    ],
                },
            }
        ],
        total_hits=1,
        took_ms=10,
        search_after="next-granule-token",
        page_size=1,
    )

    captured = {}

    def fake_search_cmr(**kwargs):
        captured.update(kwargs)
        yield page

    monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)

    output = tool.get_granules(
        collection_concept_id="C123-PROV",
    )

    assert captured["concept_type"] == "granule"
    assert captured["search_params"]["collection_concept_id"] == "C123-PROV"
    assert captured["page_size"] == 10
    assert output["status"] == "success"
    assert output["total_hits"] == 1
    assert output["granules"][0]["concept_id"] == "G123-PROV"
    assert output["granules"][0]["collection_concept_id"] == "C123-PROV"
    assert output["granules"][0]["granule_ur"] == "MOD11A1.A2024001.h00v08.061"
    assert output["granules"][0]["access_urls"] == [
        "https://example.com/data.hdf",
        "https://example.com/download.hdf",
    ]


def test_get_granules_uses_post_for_spatial_search(monkeypatch):
    """Spatial granule searches should switch to POST with a shapefile payload."""
    tool = _load_tool()
    page = CMRSearchResponse(items=[], total_hits=0, took_ms=7, search_after=None, page_size=0)

    captured = {}

    def fake_search_cmr(**kwargs):
        captured.update(kwargs)
        yield page

    monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)

    output = tool.get_granules(
        collection_concept_id="C123-PROV",
        spatial_wkt_geometry="POINT(-75 40)",
    )

    assert captured["method"] == "POST"
    assert captured["files"] is not None
    assert output["status"] == "no_results"


def test_get_granules_includes_temporal_filter(monkeypatch):
    """Temporal bounds should map into CMR temporal parameter."""
    tool = _load_tool()
    page = CMRSearchResponse(items=[], total_hits=0, took_ms=7, search_after=None, page_size=0)

    captured = {}

    def fake_search_cmr(**kwargs):
        captured.update(kwargs)
        yield page

    monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)

    output = tool.get_granules(
        collection_concept_id="C123-PROV",
        temporal_start_date="2024-01-01T00:00:00Z",
        temporal_end_date="2024-01-31T23:59:59Z",
    )

    assert captured["search_params"]["temporal"] == "2024-01-01T00:00:00Z,2024-01-31T23:59:59Z"
    assert output["status"] == "no_results"


def test_get_granules_returns_error_on_cmr_failure(monkeypatch):
    """CMR failures should be converted into stable tool errors."""
    tool = _load_tool()

    def fake_search_cmr(**_kwargs):
        raise CMRError("CMR granule request failed")
        yield  # pragma: no cover

    monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)

    output = tool.get_granules(collection_concept_id="C123-PROV")

    assert output["status"] == "error"
    assert output["error_message"] == "CMR granule request failed"


def test_get_granules_returns_no_results_when_cmr_yields_nothing(monkeypatch):
    """An empty CMR iterator should map to no_results."""
    tool = _load_tool()

    def fake_search_cmr(**_kwargs):
        return
        yield  # pragma: no cover

    monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)

    output = tool.get_granules(collection_concept_id="C123-PROV")

    assert output["status"] == "no_results"


def test_get_granules_returns_error_on_unexpected_failure(monkeypatch):
    """Unexpected failures should still return a stable tool error payload."""
    tool = _load_tool()

    def fake_search_cmr(**_kwargs):
        raise RuntimeError("unexpected granule failure")
        yield  # pragma: no cover

    monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)

    output = tool.get_granules(collection_concept_id="C123-PROV")

    assert output["status"] == "error"
    assert output["error_message"] == "An unexpected internal error occurred during granule search."


def test_get_granules_returns_error_on_invalid_spatial_wkt():
    """Invalid WKT should be returned as a stable tool error payload."""
    tool = _load_tool()

    output = tool.get_granules(
        collection_concept_id="C123-PROV",
        spatial_wkt_geometry="POINT((1 2))",
    )

    assert output["status"] == "error"
    assert "Invalid WKT geometry" in output["error_message"]


def test_get_granules_includes_cloud_cover_max_only(monkeypatch):
    """Setting only cloud_cover_max should produce a CMR cloud_cover param like ',20'."""
    tool = _load_tool()
    page = CMRSearchResponse(items=[], total_hits=0, took_ms=5, search_after=None, page_size=0)

    captured = {}

    def fake_search_cmr(**kwargs):
        captured.update(kwargs)
        yield page

    monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)

    output = tool.get_granules(
        collection_concept_id="C123-PROV",
        cloud_cover_max=20,
    )

    assert captured["search_params"]["cloud_cover"] == ",20"
    assert output["status"] == "no_results"


def test_get_granules_includes_cloud_cover_min_and_max(monkeypatch):
    """Setting both cloud_cover_min and cloud_cover_max should produce '10,50'."""
    tool = _load_tool()
    page = CMRSearchResponse(items=[], total_hits=0, took_ms=5, search_after=None, page_size=0)

    captured = {}

    def fake_search_cmr(**kwargs):
        captured.update(kwargs)
        yield page

    monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)

    output = tool.get_granules(
        collection_concept_id="C123-PROV",
        cloud_cover_min=10,
        cloud_cover_max=50,
    )

    assert captured["search_params"]["cloud_cover"] == "10,50"
    assert output["status"] == "no_results"


def test_get_granules_includes_cloud_cover_min_only(monkeypatch):
    """Setting only cloud_cover_min should produce '80,'."""
    tool = _load_tool()
    page = CMRSearchResponse(items=[], total_hits=0, took_ms=5, search_after=None, page_size=0)

    captured = {}

    def fake_search_cmr(**kwargs):
        captured.update(kwargs)
        yield page

    monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)

    output = tool.get_granules(
        collection_concept_id="C123-PROV",
        cloud_cover_min=80,
    )

    assert captured["search_params"]["cloud_cover"] == "80,"
    assert output["status"] == "no_results"


def test_get_granules_omits_cloud_cover_when_not_provided(monkeypatch):
    """When neither cloud_cover param is set, no cloud_cover key should appear."""
    tool = _load_tool()
    page = CMRSearchResponse(items=[], total_hits=0, took_ms=5, search_after=None, page_size=0)

    captured = {}

    def fake_search_cmr(**kwargs):
        captured.update(kwargs)
        yield page

    monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)

    tool.get_granules(collection_concept_id="C123-PROV")

    assert "cloud_cover" not in captured["search_params"]


def test_get_granules_rejects_cloud_cover_out_of_range():
    """Cloud cover values outside 0-100 should produce a validation error."""
    tool = _load_tool()

    output = tool.get_granules(
        collection_concept_id="C123-PROV",
        cloud_cover_max=150,
    )
    assert output["status"] == "error"

    output = tool.get_granules(
        collection_concept_id="C123-PROV",
        cloud_cover_min=-10,
    )
    assert output["status"] == "error"


def test_get_granules_calls_trace_update(monkeypatch):
    """Tool should emit Langfuse trace updates using the shared helper."""
    tool = _load_tool()
    page = CMRSearchResponse(items=[], total_hits=0, took_ms=5, search_after=None, page_size=0)

    def fake_search_cmr(**_kwargs):
        yield page

    monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)

    with patch.object(tool, "trace_update") as mock_trace_update:
        output = tool.get_granules(collection_concept_id="C123-PROV")

    assert output["status"] == "no_results"
    assert mock_trace_update.called


# --- pagination ---


def _make_granule_item(concept_id="G1-PROV"):
    """Minimal UMM granule item for pagination/field tests."""
    return {
        "meta": {"concept-id": concept_id, "parent-collection-id": "C1-PROV"},
        "umm": {"GranuleUR": f"granule-{concept_id}"},
    }


def test_get_granules_returns_next_cursor_when_page_is_full(monkeypatch):
    """next_cursor must be set when items == limit and search_after token is present."""
    tool = _load_tool()
    page = CMRSearchResponse(
        items=[_make_granule_item()],
        total_hits=5,
        took_ms=5,
        search_after="tok-abc",
        page_size=1,
    )
    monkeypatch.setattr(tool, "search_cmr", lambda **_: iter([page]))

    output = tool.get_granules(collection_concept_id="C1-PROV", limit=1)

    assert output["next_cursor"] is not None


def test_get_granules_returns_no_cursor_on_last_page(monkeypatch):
    """next_cursor must be None when items < limit."""
    tool = _load_tool()
    page = CMRSearchResponse(
        items=[_make_granule_item()],
        total_hits=1,
        took_ms=5,
        search_after="tok-xyz",
        page_size=1,
    )
    monkeypatch.setattr(tool, "search_cmr", lambda **_: iter([page]))

    output = tool.get_granules(collection_concept_id="C1-PROV", limit=5)

    assert output["next_cursor"] is None


def test_get_granules_cursor_passes_search_after(monkeypatch):
    """A valid CMR cursor must decode and pass search_after to the backend."""
    from util.pagination import encode_cursor

    tool = _load_tool()
    page = CMRSearchResponse(items=[], total_hits=0, took_ms=5, search_after=None, page_size=0)
    captured = {}

    def fake_search_cmr(**kwargs):
        captured.update(kwargs)
        yield page

    monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)

    cursor = encode_cursor(
        "cmr", {"token": "some-granule-token", "params": {"collection_concept_id": "C1-PROV"}}
    )
    tool.get_granules(collection_concept_id="C1-PROV", cursor=cursor)

    assert captured.get("search_after") == "some-granule-token"


def test_get_granules_passes_limit_as_page_size(monkeypatch):
    """The limit param must be forwarded to CMR as page_size."""
    tool = _load_tool()
    page = CMRSearchResponse(items=[], total_hits=0, took_ms=5, search_after=None, page_size=0)
    captured = {}

    def fake_search_cmr(**kwargs):
        captured.update(kwargs)
        yield page

    monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)

    tool.get_granules(collection_concept_id="C1-PROV", limit=20)

    assert captured.get("page_size") == 20


def test_get_granules_returns_error_on_invalid_cursor(monkeypatch):
    """An invalid cursor string must produce a clean error response, not an exception."""
    tool = _load_tool()
    page = CMRSearchResponse(items=[], total_hits=0, took_ms=5, search_after=None, page_size=0)
    monkeypatch.setattr(tool, "search_cmr", lambda **_: iter([page]))

    output = tool.get_granules(collection_concept_id="C1-PROV", cursor="not-valid-cursor!@#")

    assert output["status"] == "error"
    assert "cursor" in output["error_message"].lower()


def test_get_granules_returns_error_on_cross_backend_cursor(monkeypatch):
    """A KMS cursor passed to get_granules must produce a clean error response."""
    from util.pagination import encode_cursor

    tool = _load_tool()
    page = CMRSearchResponse(items=[], total_hits=0, took_ms=5, search_after=None, page_size=0)
    monkeypatch.setattr(tool, "search_cmr", lambda **_: iter([page]))

    kms_cursor = encode_cursor("kms", 20)
    output = tool.get_granules(collection_concept_id="C1-PROV", cursor=kms_cursor)

    assert output["status"] == "error"
    assert "cursor" in output["error_message"].lower()


# --- field filtering ---


def test_get_granules_fields_filtering_keeps_mandatory_fields(monkeypatch):
    """fields param must keep only requested fields plus concept_id and granule_ur."""
    tool = _load_tool()
    page = CMRSearchResponse(
        items=[_make_granule_item()],
        total_hits=1,
        took_ms=5,
        search_after=None,
        page_size=1,
    )
    monkeypatch.setattr(tool, "search_cmr", lambda **_: iter([page]))

    output = tool.get_granules(collection_concept_id="C1-PROV", fields=["time_start"])

    item = output["granules"][0]
    assert "concept_id" in item
    assert "granule_ur" in item
    assert "time_start" in item
    assert "provider_id" not in item


def test_get_granules_fields_empty_returns_all_fields(monkeypatch):
    """When fields is empty, all normalized fields must be present."""
    tool = _load_tool()
    page = CMRSearchResponse(
        items=[_make_granule_item()],
        total_hits=1,
        took_ms=5,
        search_after=None,
        page_size=1,
    )
    monkeypatch.setattr(tool, "search_cmr", lambda **_: iter([page]))

    output = tool.get_granules(collection_concept_id="C1-PROV", fields=[])

    item = output["granules"][0]
    assert "provider_id" in item
    assert "time_start" in item


# --- new search params ---


def test_get_granules_day_night_flag_param(monkeypatch):
    """day_night_flag param must appear in CMR search_params."""
    tool = _load_tool()
    page = CMRSearchResponse(items=[], total_hits=0, took_ms=5, search_after=None, page_size=0)
    captured = {}

    def fake_search_cmr(**kwargs):
        captured.update(kwargs)
        yield page

    monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)

    tool.get_granules(collection_concept_id="C1-PROV", day_night_flag="DAY")

    assert captured["search_params"].get("day_night_flag") == "DAY"


def test_get_granules_sort_key_param(monkeypatch):
    """sort_key param must appear in CMR search_params."""
    tool = _load_tool()
    page = CMRSearchResponse(items=[], total_hits=0, took_ms=5, search_after=None, page_size=0)
    captured = {}

    def fake_search_cmr(**kwargs):
        captured.update(kwargs)
        yield page

    monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)

    tool.get_granules(collection_concept_id="C1-PROV", sort_key="-start_date")

    assert captured["search_params"].get("sort_key") == "-start_date"


# --- new response fields ---


def _make_rich_granule_item():
    """UMM granule item with all new Phase 2 fields populated."""
    return {
        "meta": {"concept-id": "G1-PROV", "parent-collection-id": "C1-PROV"},
        "umm": {
            "GranuleUR": "granule-G1-PROV",
            "DataGranule": {
                "ProductionDateTime": "2024-01-15T10:00:00Z",
                "DayNightFlag": "DAY",
            },
            "OrbitCalculatedSpatialDomains": [
                {
                    "OrbitalModelName": "MODIS",
                    "OrbitNumber": 12345,
                    "EquatorCrossingLongitude": -75.5,
                    "EquatorCrossingDateTime": "2024-01-01T06:00:00Z",
                }
            ],
            "AdditionalAttributes": [
                {"Name": "TILE_ID", "Values": ["h18v04"]},
                {"Name": "QAPERCENTCLOUDCOVER", "Values": ["5"]},
            ],
        },
    }


def test_get_granules_new_response_fields_present(monkeypatch):
    """production_date, orbit_info, and additional_attributes must appear in normalized output."""
    tool = _load_tool()
    page = CMRSearchResponse(
        items=[_make_rich_granule_item()],
        total_hits=1,
        took_ms=5,
        search_after=None,
        page_size=1,
    )
    monkeypatch.setattr(tool, "search_cmr", lambda **_: iter([page]))

    output = tool.get_granules(collection_concept_id="C1-PROV")

    item = output["granules"][0]
    assert "production_date" in item
    assert item["production_date"] is not None
    assert "orbit_info" in item
    assert item["orbit_info"][0]["orbit_number"] == 12345
    assert "additional_attributes" in item
    assert item["additional_attributes"][0]["name"] == "TILE_ID"


def test_get_granules_old_format_cursor_returns_error(monkeypatch):
    """An old-format (scalar value) cursor must return a clean error."""
    from util.pagination import encode_cursor

    tool = _load_tool()
    page = CMRSearchResponse(items=[], total_hits=0, took_ms=5, search_after=None, page_size=0)
    monkeypatch.setattr(tool, "search_cmr", lambda **_: iter([page]))

    old_cursor = encode_cursor("cmr", "some-legacy-token")
    output = tool.get_granules(collection_concept_id="C1-PROV", cursor=old_cursor)

    assert output["status"] == "error"
    assert "outdated" in output["error_message"].lower()


def test_get_granules_cursor_override():
    from tools.get_granules.tool import get_granules
    from util.pagination import encode_cursor

    cursor = encode_cursor(
        "cmr",
        {
            "token": "tok-abc",
            "params": {"collection_concept_id": "C1-PROV", "temporal": "2024-01-01,2024-01-31"},
        },
    )
    res = get_granules(
        collection_concept_id="C1-PROV", temporal_start_date="2025-01-01T00:00:00Z", cursor=cursor
    )
    assert res["status"] == "error"
    assert "query-scoped" in res["error_message"]


def test_get_granules_validation_error():
    from tools.get_granules.tool import get_granules

    res = get_granules(
        collection_concept_id="C123-PROV", limit=100
    )  # limit=100 triggers validation error
    assert res["status"] == "error"


def test_get_granules_wkt_error():
    from tools.get_granules.tool import get_granules

    res = get_granules(collection_concept_id="C1-PROV", spatial_wkt_geometry="INVALID WKT")
    assert res["status"] == "error"
    assert "Invalid WKT" in res["error_message"]


def test_get_granules_cursor_post():
    from unittest.mock import patch

    from tools.get_granules.tool import get_granules
    from util.cmr.client import CMRSearchResponse
    from util.pagination import encode_cursor

    c = encode_cursor(
        "cmr",
        {"token": "x", "spatial": "POINT(0 0)", "params": {"collection_concept_id": "C1-PROV"}},
    )
    with patch("tools.get_granules.tool.search_cmr") as mock_search:
        mock_search.return_value = iter(
            [CMRSearchResponse(items=[], total_hits=0, took_ms=5, search_after=None, page_size=0)]
        )
        get_granules(collection_concept_id="C1-PROV", spatial_wkt_geometry="POINT(0 0)", cursor=c)
        mock_search.assert_called_once()
