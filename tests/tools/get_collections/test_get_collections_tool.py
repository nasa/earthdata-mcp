"""Tests for the get_collections MCP tool."""

import importlib

import pytest

from util.cmr.client import CMRError, CMRSearchResponse


def _load_tool():
    return importlib.import_module("tools.get_collections.tool")


def test_get_collections_requires_search_criteria():
    """The tool should reject empty collection searches."""
    tool = _load_tool()

    with pytest.raises(ValueError, match="At least one of query"):
        tool.get_collections()


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
        query="land surface temperature",
        page_size=5,
        search_after="seed-token",
    )

    assert captured["concept_type"] == "collection"
    assert captured["search_params"]["keyword"] == "land surface temperature"
    assert captured["search_after"] == "seed-token"
    assert captured["method"] == "GET"
    assert output["status"] == "success"
    assert output["total_hits"] == 1
    assert output["search_after"] == "next-token"
    assert output["collections"][0]["concept_id"] == "C123-PROV"
    assert output["collections"][0]["short_name"] == "MOD11A1"
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

    output = tool.get_collections(query="modis", spatial_wkt_geometry="POINT(-75 40)")

    assert captured["method"] == "POST"
    assert captured["files"] is not None
    assert output["status"] == "no_results"


def test_get_collections_returns_error_on_cmr_failure(monkeypatch):
    """CMR failures should be converted into stable tool errors."""
    tool = _load_tool()

    def fake_search_cmr(**_kwargs):
        raise CMRError("CMR request failed")
        yield  # pragma: no cover

    monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)

    output = tool.get_collections(query="modis")

    assert output["status"] == "error"
    assert output["error_message"] == "CMR request failed"


def test_get_collections_accepts_string_page_size(monkeypatch):
    """Numeric string page_size should be accepted and coerced before CMR call."""
    tool = _load_tool()
    page = CMRSearchResponse(items=[], total_hits=0, took_ms=4, search_after=None, page_size=0)

    captured = {}

    def fake_search_cmr(**kwargs):
        captured.update(kwargs)
        yield page

    monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)

    output = tool.get_collections(query="ascat soil moisture", page_size="10")

    assert captured["page_size"] == 10
    assert output["status"] == "no_results"
