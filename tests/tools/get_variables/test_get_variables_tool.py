"""Unit tests for the get_variables MCP tool."""

import importlib
from unittest.mock import patch

from models.tools.cmr_search import SearchStatus
from util.cmr.client import CMRError, CMRSearchResponse


def _load_tool():
    return importlib.import_module("tools.get_variables.tool")


def test_get_variables_input_validation_missing_args(monkeypatch):
    """Test that get_variables fails gracefully when no arguments are provided."""
    tool = _load_tool()

    result = tool.get_variables()

    assert result["status"] == SearchStatus.ERROR
    assert "Must provide either a collection_concept_id or a keyword" in result["error_message"]


def test_get_variables_success_keyword(monkeypatch):
    """Test successful variable lookup by keyword."""
    tool = _load_tool()

    var_page = CMRSearchResponse(
        items=[
            {
                "meta": {"concept-id": "V12345-PROV"},
                "umm": {
                    "Name": "SST",
                    "LongName": "Sea Surface Temperature",
                    "Definition": "Temperature of the sea surface",
                    "DataType": "float32",
                    "Units": "Kelvin",
                    "Scale": 0.01,
                    "Offset": 273.15,
                },
            }
        ],
        total_hits=1,
        took_ms=5,
        search_after=None,
        page_size=10,
    )

    captured = []

    def fake_search_cmr(**kwargs):
        captured.append(kwargs)
        yield var_page

    monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)

    result = tool.get_variables(keyword="SST")

    assert result["status"] == SearchStatus.SUCCESS
    assert result["total_hits"] == 1
    assert len(result["variables"]) == 1

    var = result["variables"][0]
    assert var["concept_id"] == "V12345-PROV"
    assert var["name"] == "SST"
    assert var["scale"] == 0.01
    assert var["offset"] == 273.15

    # Verify search_cmr was called correctly for variables
    assert len(captured) == 1
    assert captured[0]["concept_type"] == "variable"
    assert captured[0]["search_params"] == {"keyword": "SST"}


def test_get_variables_success_collection_concept_id(monkeypatch):
    """Test successful variable lookup by collection concept ID."""
    tool = _load_tool()

    coll_page = CMRSearchResponse(
        items=[
            {"meta": {"concept-id": "C99999-PROV", "associations": {"variables": ["V67890-PROV"]}}}
        ],
        total_hits=1,
        took_ms=5,
        search_after=None,
        page_size=1,
    )

    var_page = CMRSearchResponse(
        items=[
            {
                "meta": {"concept-id": "V67890-PROV"},
                "umm": {
                    "Name": "NDVI",
                    "LongName": "Normalized Difference Vegetation Index",
                    "ValidRanges": [{"Min": -1.0, "Max": 1.0}],
                    "Dimensions": [{"Name": "lat", "Size": 180}, {"Name": "lon", "Size": 360}],
                },
            }
        ],
        total_hits=1,
        took_ms=5,
        search_after=None,
        page_size=10,
    )

    captured = []

    def fake_search_cmr(**kwargs):
        captured.append(kwargs)
        if kwargs["concept_type"] == "collection":
            yield coll_page
        else:
            yield var_page

    monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)

    result = tool.get_variables(collection_concept_id="C99999-PROV")

    assert result["status"] == SearchStatus.SUCCESS
    assert len(result["variables"]) == 1

    var = result["variables"][0]
    assert var["concept_id"] == "V67890-PROV"
    assert var["name"] == "NDVI"
    assert var["valid_ranges"] == [{"Min": -1.0, "Max": 1.0}]
    assert var["dimensions"] == [{"Name": "lat", "Size": 180}, {"Name": "lon", "Size": 360}]

    # Verify search_cmr was called correctly (collection, then variable)
    assert len(captured) == 2
    assert captured[0]["concept_type"] == "collection"
    assert captured[0]["search_params"] == {"concept_id": "C99999-PROV"}

    assert captured[1]["concept_type"] == "variable"
    assert captured[1]["search_params"] == {"concept_id[]": ["V67890-PROV"]}


def test_get_variables_success_collection_and_keyword(monkeypatch):
    """Test successful variable lookup using both collection concept ID and keyword."""
    tool = _load_tool()

    coll_page = CMRSearchResponse(
        items=[
            {
                "meta": {
                    "concept-id": "C99999-PROV",
                    "associations": {"variables": ["V67890-PROV", "V11111-PROV"]},
                }
            }
        ],
        total_hits=1,
        took_ms=5,
        search_after=None,
        page_size=1,
    )

    var_page = CMRSearchResponse(
        items=[
            {
                "meta": {"concept-id": "V67890-PROV"},
                "umm": {
                    "Name": "NDVI",
                    "LongName": "Normalized Difference Vegetation Index",
                },
            }
        ],
        total_hits=1,
        took_ms=5,
        search_after=None,
        page_size=10,
    )

    captured = []

    def fake_search_cmr(**kwargs):
        captured.append(kwargs)
        if kwargs["concept_type"] == "collection":
            yield coll_page
        else:
            yield var_page

    monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)

    result = tool.get_variables(collection_concept_id="C99999-PROV", keyword="NDVI")

    assert result["status"] == SearchStatus.SUCCESS
    assert result["total_hits"] == 1  # Intersection count
    assert len(result["variables"]) == 1

    var = result["variables"][0]
    assert var["concept_id"] == "V67890-PROV"
    assert var["name"] == "NDVI"

    assert len(captured) == 2
    assert captured[0]["concept_type"] == "collection"
    assert captured[0]["search_params"] == {"concept_id": "C99999-PROV"}

    assert captured[1]["concept_type"] == "variable"
    assert captured[1]["search_params"] == {
        "concept_id[]": ["V67890-PROV", "V11111-PROV"],
        "keyword": "NDVI",
    }


def test_get_variables_collection_and_keyword_empty_associations(monkeypatch):
    """Test get_variables when both collection and keyword are provided, but collection has no variables."""
    tool = _load_tool()

    page = CMRSearchResponse(
        items=[{"meta": {"concept-id": "C99999-PROV", "associations": {}}}],
        total_hits=1,
        took_ms=5,
        search_after=None,
        page_size=1,
    )

    def fake_search_cmr(**kwargs):
        yield page

    monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)

    result = tool.get_variables(collection_concept_id="C99999-PROV", keyword="SST")

    assert result["status"] == SearchStatus.NO_RESULTS
    assert result["variables"] == []


def test_get_variables_no_results(monkeypatch):
    """Test get_variables when CMR returns no results."""
    tool = _load_tool()

    page = CMRSearchResponse(
        items=[],
        total_hits=0,
        took_ms=5,
        search_after=None,
        page_size=10,
    )

    def fake_search_cmr(**kwargs):
        yield page

    monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)

    result = tool.get_variables(keyword="NonExistentVariable")

    assert result["status"] == SearchStatus.NO_RESULTS
    assert result["variables"] == []


def test_get_variables_cmr_error(monkeypatch):
    """Test get_variables handling of CMR API errors."""
    tool = _load_tool()

    def fake_search_cmr(**kwargs):
        raise CMRError("CMR API is down")
        yield

    monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)

    result = tool.get_variables(keyword="SST")

    assert result["status"] == SearchStatus.ERROR
    assert "CMR API is down" in result["error_message"]


def test_get_variables_returns_error_on_unexpected_failure(monkeypatch):
    """Test unexpected internal error handling."""
    tool = _load_tool()

    def fake_search_cmr(**kwargs):
        raise RuntimeError("unexpected failure")
        yield  # pragma: no cover

    monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)

    result = tool.get_variables(keyword="SST")

    assert result["status"] == SearchStatus.ERROR
    assert "unexpected internal error" in result["error_message"]


def test_get_variables_calls_trace_update(monkeypatch):
    """Test telemetry tracing."""
    tool = _load_tool()

    page = CMRSearchResponse(items=[], total_hits=0, took_ms=5, search_after=None, page_size=10)

    def fake_search_cmr(**kwargs):
        yield page

    monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)

    with patch.object(tool, "trace_update") as mock_trace_update:
        tool.get_variables(keyword="SST")

    assert mock_trace_update.called


def test_get_variables_collection_cmr_error(monkeypatch):
    """Test get_variables handling of CMRError during collection lookup."""
    tool = _load_tool()

    def fake_search_cmr(**kwargs):
        raise CMRError("Collection search failed")
        yield

    monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)

    result = tool.get_variables(collection_concept_id="C99999-PROV")

    assert result["status"] == SearchStatus.ERROR
    assert "Collection search failed" in result["error_message"]


def test_get_variables_collection_unexpected_error(monkeypatch):
    """Test get_variables handling of unexpected error during collection lookup."""
    tool = _load_tool()

    def fake_search_cmr(**kwargs):
        raise RuntimeError("Boom")
        yield

    monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)

    result = tool.get_variables(collection_concept_id="C99999-PROV")

    assert result["status"] == SearchStatus.ERROR
    assert "unexpected internal error occurred during collection lookup" in result["error_message"]


def test_get_variables_collection_empty_items(monkeypatch):
    """Test get_variables when collection page has no items."""
    tool = _load_tool()

    page = CMRSearchResponse(
        items=[],
        total_hits=0,
        took_ms=5,
        search_after=None,
        page_size=1,
    )

    def fake_search_cmr(**kwargs):
        yield page

    monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)

    result = tool.get_variables(collection_concept_id="C99999-PROV")

    assert result["status"] == SearchStatus.NO_RESULTS
    assert result["variables"] == []


def test_get_variables_collection_no_variable_associations(monkeypatch):
    """Test get_variables when collection exists but has no variable associations."""
    tool = _load_tool()

    page = CMRSearchResponse(
        items=[{"meta": {"concept-id": "C99999-PROV", "associations": {}}}],
        total_hits=1,
        took_ms=5,
        search_after=None,
        page_size=1,
    )

    def fake_search_cmr(**kwargs):
        yield page

    monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)

    result = tool.get_variables(collection_concept_id="C99999-PROV")

    assert result["status"] == SearchStatus.NO_RESULTS
    assert result["variables"] == []


def test_get_variables_variable_search_empty_items(monkeypatch):
    """Test get_variables when variable search yields empty items after successful collection lookup."""
    tool = _load_tool()

    coll_page = CMRSearchResponse(
        items=[
            {"meta": {"concept-id": "C99999-PROV", "associations": {"variables": ["V67890-PROV"]}}}
        ],
        total_hits=1,
        took_ms=5,
        search_after=None,
        page_size=1,
    )

    var_page = CMRSearchResponse(
        items=[],
        total_hits=0,
        took_ms=5,
        search_after=None,
        page_size=10,
    )

    def fake_search_cmr(**kwargs):
        if kwargs["concept_type"] == "collection":
            yield coll_page
        else:
            yield var_page

    monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)

    result = tool.get_variables(collection_concept_id="C99999-PROV")

    assert result["status"] == SearchStatus.NO_RESULTS
    assert result["variables"] == []
