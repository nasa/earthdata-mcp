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
