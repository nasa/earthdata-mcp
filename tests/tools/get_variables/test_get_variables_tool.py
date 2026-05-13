"""Tests for get_variables_tool."""

import importlib
from unittest.mock import patch

import util.cmr.search_tools as _search_tools_mod
from models.tools.cmr_search import SearchStatus
from util.cmr.client import CMRError, CMRSearchResponse
from util.pagination import encode_cursor, resolve_cursor


def _load_tool():
    return importlib.import_module("tools.get_variables.tool")


def _patch_search_cmr(monkeypatch, tool_module, fake_fn):
    """Patch both the local module search_cmr and the utils for fetch_association_ids."""
    monkeypatch.setattr(tool_module, "search_cmr", fake_fn)
    monkeypatch.setattr(_search_tools_mod, "search_cmr", fake_fn)


def test_get_variables_input_validation_missing_args(monkeypatch):
    """Test get_variables fails when neither collection_concept_id nor keyword is provided."""
    tool = _load_tool()

    result = tool.get_variables()

    assert result["status"] == SearchStatus.ERROR
    assert "Must provide either a collection_concept_id or a keyword" in result["error_message"]


def test_get_variables_success_keyword(monkeypatch):
    """Test successful variable lookup using a keyword."""
    tool = _load_tool()

    var_page = CMRSearchResponse(
        items=[
            {
                "meta": {"concept-id": "V12345-PROV"},
                "umm": {
                    "Name": "SST",
                    "LongName": "Sea Surface Temperature",
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

    _patch_search_cmr(monkeypatch, tool, fake_search_cmr)

    result = tool.get_variables(keyword="SST")

    assert result["status"] == SearchStatus.SUCCESS
    assert result["total_hits"] == 1
    assert len(result["variables"]) == 1
    assert result["next_cursor"] is None

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
            {
                "meta": {
                    "concept-id": "C99999-PROV",
                    "associations": {"variables": ["V67890-PROV"]},
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

    _patch_search_cmr(monkeypatch, tool, fake_search_cmr)

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

    _patch_search_cmr(monkeypatch, tool, fake_search_cmr)

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

    coll_page = CMRSearchResponse(
        items=[{"meta": {"concept-id": "C99999-PROV", "associations": {}}}],
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

    captured = []

    def fake_search_cmr(**kwargs):
        captured.append(kwargs)
        if kwargs["concept_type"] == "collection":
            yield coll_page
        else:
            yield var_page

    _patch_search_cmr(monkeypatch, tool, fake_search_cmr)

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

    _patch_search_cmr(monkeypatch, tool, fake_search_cmr)

    result = tool.get_variables(keyword="NonExistentVariable")

    assert result["status"] == SearchStatus.NO_RESULTS
    assert result["variables"] == []


def test_get_variables_cmr_error(monkeypatch):
    """Test get_variables handling of CMR API errors."""
    tool = _load_tool()

    def fake_search_cmr(**kwargs):
        raise CMRError("CMR API is down")
        yield

    _patch_search_cmr(monkeypatch, tool, fake_search_cmr)

    result = tool.get_variables(keyword="SST")

    assert result["status"] == SearchStatus.ERROR
    assert "CMR API is down" in result["error_message"]


def test_get_variables_returns_error_on_unexpected_failure(monkeypatch):
    """Test unexpected internal error handling."""
    tool = _load_tool()

    def fake_search_cmr(**kwargs):
        raise RuntimeError("unexpected failure")
        yield  # pragma: no cover

    _patch_search_cmr(monkeypatch, tool, fake_search_cmr)

    result = tool.get_variables(keyword="SST")

    assert result["status"] == SearchStatus.ERROR
    assert "unexpected internal error" in result["error_message"]


def test_get_variables_calls_trace_update(monkeypatch):
    """Test telemetry tracing."""
    tool = _load_tool()

    page = CMRSearchResponse(items=[], total_hits=0, took_ms=5, search_after=None, page_size=10)

    def fake_search_cmr(**kwargs):
        yield page

    _patch_search_cmr(monkeypatch, tool, fake_search_cmr)

    with patch.object(tool, "trace_update") as mock_trace_update:
        tool.get_variables(keyword="SST")

    assert mock_trace_update.called


def test_get_variables_collection_cmr_error(monkeypatch):
    """Test get_variables handling of CMRError during collection lookup."""
    tool = _load_tool()

    def fake_search_cmr(**kwargs):
        raise CMRError("Collection search failed")
        yield

    _patch_search_cmr(monkeypatch, tool, fake_search_cmr)

    result = tool.get_variables(collection_concept_id="C99999-PROV")

    assert result["status"] == SearchStatus.ERROR
    assert "Collection search failed" in result["error_message"]


def test_get_variables_collection_unexpected_error(monkeypatch):
    """Test get_variables handling of unexpected error during collection lookup."""
    tool = _load_tool()

    def fake_search_cmr(**kwargs):
        raise RuntimeError("Boom")
        yield

    _patch_search_cmr(monkeypatch, tool, fake_search_cmr)

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

    _patch_search_cmr(monkeypatch, tool, fake_search_cmr)

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

    _patch_search_cmr(monkeypatch, tool, fake_search_cmr)

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

    _patch_search_cmr(monkeypatch, tool, fake_search_cmr)

    result = tool.get_variables(collection_concept_id="C99999-PROV")

    assert result["status"] == SearchStatus.NO_RESULTS
    assert result["variables"] == []


def test_get_variables_pagination_first_page(monkeypatch):
    """Test get_variables returns next_cursor when there are more results."""
    tool = _load_tool()

    coll_page = CMRSearchResponse(
        items=[
            {
                "meta": {
                    "concept-id": "C99999-PROV",
                    "associations": {"variables": ["V1-PROV", "V2-PROV", "V3-PROV"]},
                }
            }
        ],
        total_hits=1,
        took_ms=5,
        search_after=None,
        page_size=1,
    )

    var_page = CMRSearchResponse(
        items=[{"meta": {"concept-id": "V1-PROV"}}, {"meta": {"concept-id": "V2-PROV"}}],
        total_hits=3,
        took_ms=5,
        search_after="tok-v1",
        page_size=2,
    )

    def fake_search_cmr(**kwargs):
        if kwargs["concept_type"] == "collection":
            yield coll_page
        else:
            yield var_page

    _patch_search_cmr(monkeypatch, tool, fake_search_cmr)

    result = tool.get_variables(collection_concept_id="C99999-PROV", limit=2)

    assert result["status"] == SearchStatus.SUCCESS
    assert len(result["variables"]) == 2
    assert result["next_cursor"] is not None
    parsed = resolve_cursor(result["next_cursor"], "cmr")
    assert parsed["token"] == "tok-v1"
    assert result["total_hits"] == 3


def test_get_variables_pagination_second_page(monkeypatch):
    """Test get_variables uses search_after from decoded cursor on second page."""
    tool = _load_tool()

    coll_page = CMRSearchResponse(
        items=[
            {
                "meta": {
                    "concept-id": "C99999-PROV",
                    "associations": {"variables": ["V1-PROV", "V2-PROV", "V3-PROV"]},
                }
            }
        ],
        total_hits=1,
        took_ms=5,
        search_after=None,
        page_size=1,
    )

    var_page_last = CMRSearchResponse(
        items=[{"meta": {"concept-id": "V3-PROV"}}],
        total_hits=3,
        took_ms=5,
        search_after=None,
        page_size=2,
    )

    captured = []

    def fake_search_cmr(**kwargs):
        captured.append(kwargs)
        if kwargs["concept_type"] == "collection":
            yield coll_page
        else:
            yield var_page_last

    _patch_search_cmr(monkeypatch, tool, fake_search_cmr)

    cursor = encode_cursor(
        "cmr",
        {
            "token": "tok-v1",
            "params": {"concept_id[]": ["V1-PROV", "V2-PROV", "V3-PROV"]},
            "inputs": {"collection_concept_id": "C99999-PROV"},
        },
    )
    result = tool.get_variables(collection_concept_id="C99999-PROV", cursor=cursor, limit=2)

    assert result["status"] == SearchStatus.SUCCESS
    assert result["next_cursor"] is None
    assert len(captured) == 1
    assert captured[0]["search_after"] == "tok-v1"


def test_get_variables_invalid_cursor(monkeypatch):
    """Test get_variables returns error for an invalid cursor."""
    tool = _load_tool()

    result = tool.get_variables(keyword="SST", cursor="not-valid-base64!!!")

    assert result["status"] == SearchStatus.ERROR
    assert "Invalid pagination cursor" in result["error_message"]


def test_get_variables_cross_backend_cursor(monkeypatch):
    """Test get_variables returns error if cursor is for wrong backend."""
    tool = _load_tool()

    kms_cursor = encode_cursor("kms", "some-token")
    result = tool.get_variables(keyword="SST", cursor=kms_cursor)

    assert result["status"] == SearchStatus.ERROR
    assert "not valid for this tool" in result["error_message"]


def test_get_variables_fields_filter(monkeypatch):
    """Test get_variables respects the fields filter parameter."""
    tool = _load_tool()

    var_page = CMRSearchResponse(
        items=[
            {
                "meta": {"concept-id": "V12345-PROV"},
                "umm": {
                    "Name": "SST",
                    "LongName": "Sea Surface Temperature",
                    "Units": "Kelvin",
                },
            }
        ],
        total_hits=1,
        took_ms=5,
        search_after=None,
        page_size=10,
    )

    def fake_search_cmr(**kwargs):
        yield var_page

    _patch_search_cmr(monkeypatch, tool, fake_search_cmr)
    result = tool.get_variables(keyword="SST", fields=["name"])

    assert result["status"] == SearchStatus.SUCCESS
    item = result["variables"][0]
    assert "concept_id" in item
    assert "name" in item
    assert "long_name" not in item
    assert "units" not in item


def test_get_variables_old_format_cursor_returns_error(monkeypatch):
    """An old-format (scalar string) cursor must return a clean error."""
    tool = _load_tool()

    old_cursor = encode_cursor("cmr", "some-legacy-token")
    result = tool.get_variables(keyword="SST", cursor=old_cursor)

    assert result["status"] == SearchStatus.ERROR
    assert result["next_cursor"] is None
    assert "outdated" in result["error_message"].lower()


def test_get_variables_cursor_ignores_changed_params(monkeypatch):
    """When cursor is present, stored params are used and incoming keyword ignored."""
    tool = _load_tool()

    var_page = CMRSearchResponse(
        items=[{"meta": {"concept-id": "V1"}, "umm": {"Name": "Original"}}],
        total_hits=1,
        took_ms=5,
        search_after=None,
        page_size=10,
    )
    captured = []

    def fake_search_cmr(**kwargs):
        captured.append(kwargs)
        yield var_page

    _patch_search_cmr(monkeypatch, tool, fake_search_cmr)

    cursor = encode_cursor("cmr", {"token": "tok-v1", "params": {"keyword": "original"}})
    output = tool.get_variables(keyword="changed", cursor=cursor)
    assert output["status"] == "error"
    assert "query-scoped" in output["error_message"].lower()
