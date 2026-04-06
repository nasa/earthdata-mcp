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
    assert captured["page_size"] == 20
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
