"""Tests for the get_tools MCP tool."""

import importlib
from unittest.mock import patch

from models.pagination import decode_cursor, encode_cursor
from util.cmr.client import CMRError, CMRSearchResponse


def _load_tool():
    return importlib.import_module("tools.get_tools.tool")


def _collection_page(tool_ids=None):
    """Build a collection CMRSearchResponse whose meta carries the given tool IDs."""
    associations = {}
    if tool_ids is not None:
        associations["tools"] = tool_ids
    item = {"meta": {"concept-id": "C1-PROV", "associations": associations}, "umm": {}}
    return CMRSearchResponse(items=[item], total_hits=1, took_ms=5, search_after=None, page_size=1)


def _tool_page(items=None, total_hits=1, search_after=None, page_size=10):
    """Build a tool CMRSearchResponse."""
    return CMRSearchResponse(
        items=items or [{"meta": {"concept-id": "TL1-PROV"}, "umm": {"Name": "My Tool"}}],
        total_hits=total_hits,
        took_ms=8,
        search_after=search_after,
        page_size=page_size,
    )


def _make_two_phase_mock(collection_page, tool_page):
    """Return a fake search_cmr that yields collection_page then tool_page."""

    def fake_search_cmr(**kwargs):
        if kwargs.get("concept_type") == "collection":
            yield collection_page
        else:
            yield tool_page

    return fake_search_cmr


class TestGetToolsSuccess:
    """Happy-path tests for get_tools."""

    def test_returns_success_status(self, monkeypatch):
        tool = _load_tool()
        monkeypatch.setattr(
            tool,
            "search_cmr",
            _make_two_phase_mock(_collection_page(["TL1-PROV"]), _tool_page()),
        )
        output = tool.get_tools(collection_concept_id="C1-PROV")
        assert output["status"] == "success"
        assert output["next_cursor"] is None

    def test_tools_contains_normalized_items(self, monkeypatch):
        tool = _load_tool()
        raw_item = {
            "meta": {
                "concept-id": "TL1-PROV",
                "native-id": "NATIVE-1",
                "provider-id": "PROV",
                "revision-id": 1,
            },
            "umm": {
                "Name": "Giovanni",
                "Type": "Web User Interface",
                "AccessConstraints": "Requires Earthdata Login",
            },
        }
        monkeypatch.setattr(
            tool,
            "search_cmr",
            _make_two_phase_mock(_collection_page(["TL1-PROV"]), _tool_page(items=[raw_item])),
        )
        output = tool.get_tools(collection_concept_id="C1-PROV")
        assert len(output["tools"]) == 1
        assert output["tools"][0]["concept_id"] == "TL1-PROV"
        assert output["tools"][0]["name"] == "Giovanni"
        assert output["tools"][0]["access_constraints"] == "Requires Earthdata Login"
        assert output["tools"][0]["native_id"] == "NATIVE-1"
        assert output["tools"][0]["provider_id"] == "PROV"
        assert output["tools"][0]["revision_id"] == 1
        assert output["tools"][0]["type"] == "Web User Interface"

    def test_total_hits_reflects_tool_page(self, monkeypatch):
        tool = _load_tool()
        monkeypatch.setattr(
            tool,
            "search_cmr",
            _make_two_phase_mock(
                _collection_page(["TL1-PROV", "TL2-PROV"]),
                _tool_page(total_hits=2),
            ),
        )
        output = tool.get_tools(collection_concept_id="C1-PROV")
        assert output["total_hits"] == 2
        assert "took_ms" not in output

    def test_tool_search_receives_concept_id_list(self, monkeypatch):
        tool = _load_tool()
        captured = {}

        def fake_search_cmr(**kwargs):
            captured[kwargs["concept_type"]] = kwargs
            if kwargs["concept_type"] == "collection":
                yield _collection_page(["TL1-PROV", "TL2-PROV"])
            else:
                yield _tool_page()

        monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)
        tool.get_tools(collection_concept_id="C1-PROV")
        assert captured["tool"]["search_params"]["concept_id[]"] == ["TL1-PROV", "TL2-PROV"]
        assert captured["tool"]["page_size"] == 10


class TestGetToolsNoResults:
    """Tests for no-results scenarios."""

    def test_returns_no_results_when_collection_not_found(self, monkeypatch):
        tool = _load_tool()
        empty_page = CMRSearchResponse(
            items=[], total_hits=0, took_ms=3, search_after=None, page_size=0
        )

        def fake_search_cmr(**kwargs):
            yield empty_page

        monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)
        output = tool.get_tools(collection_concept_id="C99999-MISSING")
        assert output["status"] == "no_results"
        assert output["tools"] == []

    def test_returns_no_results_when_collection_has_no_tools(self, monkeypatch):
        tool = _load_tool()

        def fake_search_cmr(**kwargs):
            yield _collection_page(tool_ids=[])

        monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)
        output = tool.get_tools(collection_concept_id="C1-PROV")
        assert output["status"] == "no_results"

    def test_returns_no_results_when_associations_key_absent(self, monkeypatch):
        tool = _load_tool()
        item = {"meta": {"concept-id": "C1-PROV"}, "umm": {}}
        page = CMRSearchResponse(
            items=[item], total_hits=1, took_ms=5, search_after=None, page_size=1
        )

        def fake_search_cmr(**kwargs):
            yield page

        monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)
        output = tool.get_tools(collection_concept_id="C1-PROV")
        assert output["status"] == "no_results"

    def test_returns_no_results_when_tool_page_is_none(self, monkeypatch):
        tool = _load_tool()

        def fake_search_cmr(**kwargs):
            if kwargs["concept_type"] == "collection":
                yield _collection_page(["TL1-PROV"])

        monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)
        output = tool.get_tools(collection_concept_id="C1-PROV")
        assert output["status"] == "no_results"


class TestGetToolsErrors:
    """Tests for error-response scenarios."""

    def test_returns_error_on_collection_cmr_error(self, monkeypatch):
        tool = _load_tool()

        def fake_search_cmr(**kwargs):
            raise CMRError("Collection lookup failed")
            yield

        monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)
        output = tool.get_tools(collection_concept_id="C1-PROV")
        assert output["status"] == "error"
        assert "Collection lookup failed" in output["error_message"]

    def test_returns_error_on_tool_cmr_error(self, monkeypatch):
        tool = _load_tool()

        def fake_search_cmr(**kwargs):
            if kwargs["concept_type"] == "collection":
                yield _collection_page(["TL1-PROV"])
            else:
                raise CMRError("Tool fetch failed")
                yield

        monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)
        output = tool.get_tools(collection_concept_id="C1-PROV")
        assert output["status"] == "error"
        assert "Tool fetch failed" in output["error_message"]

    def test_returns_error_on_input_validation(self, monkeypatch):
        tool = _load_tool()
        output = tool.get_tools(collection_concept_id="invalid_format")
        assert output["status"] == "error"
        assert "Invalid collection concept ID format" in output["error_message"]

    def test_returns_error_on_unexpected_collection_error(self, monkeypatch):
        tool = _load_tool()

        def fake_search_cmr(**kwargs):
            raise RuntimeError("Unexpected collection boom")
            yield

        monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)
        output = tool.get_tools(collection_concept_id="C1-PROV")
        assert output["status"] == "error"
        assert (
            output["error_message"]
            == "An unexpected internal error occurred during collection lookup."
        )

    def test_returns_error_on_unexpected_tool_error(self, monkeypatch):
        tool = _load_tool()

        def fake_search_cmr(**kwargs):
            if kwargs["concept_type"] == "collection":
                yield _collection_page(["TL1-PROV"])
            else:
                raise RuntimeError("Unexpected tool boom")
                yield

        monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)
        output = tool.get_tools(collection_concept_id="C1-PROV")
        assert output["status"] == "error"
        assert output["error_message"] == "An unexpected internal error occurred during tool fetch."


def test_get_tools_calls_trace_update(monkeypatch):
    """Test telemetry tracing."""
    tool = _load_tool()

    page = _collection_page([])

    def fake_search_cmr(**kwargs):
        yield page

    monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)

    with patch.object(tool, "trace_update") as mock_trace_update:
        tool.get_tools(collection_concept_id="C1-PROV")

    assert mock_trace_update.called


class TestGetToolsPagination:
    """Tests for pagination, keyword, and type params."""

    def test_no_args_returns_error(self, monkeypatch):
        tool = _load_tool()
        output = tool.get_tools()
        assert output["status"] == "error"
        assert "at least one" in output["error_message"].lower()

    def test_keyword_only(self, monkeypatch):
        tool = _load_tool()
        captured = {}

        def fake_search_cmr(**kwargs):
            captured[kwargs["concept_type"]] = kwargs
            yield _tool_page()

        monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)
        output = tool.get_tools(keyword="Giovanni")
        assert output["status"] == "success"
        assert "collection" not in captured
        assert captured["tool"]["search_params"] == {"keyword": "Giovanni"}

    def test_type_only(self, monkeypatch):
        tool = _load_tool()
        captured = {}

        def fake_search_cmr(**kwargs):
            captured[kwargs["concept_type"]] = kwargs
            yield _tool_page()

        monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)
        output = tool.get_tools(type="Downloadable Tool")
        assert output["status"] == "success"
        assert captured["tool"]["search_params"] == {"type": "Downloadable Tool"}

    def test_first_page_has_next_cursor(self, monkeypatch):
        tool = _load_tool()
        items = [
            {"meta": {"concept-id": "TL1-PROV"}, "umm": {"Name": "Tool A"}},
            {"meta": {"concept-id": "TL2-PROV"}, "umm": {"Name": "Tool B"}},
        ]

        def fake_search_cmr(**kwargs):
            if kwargs.get("concept_type") == "collection":
                yield _collection_page(["TL1-PROV", "TL2-PROV", "TL3-PROV"])
            else:
                yield _tool_page(items=items, search_after="tok-abc", page_size=2)

        monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)
        output = tool.get_tools(collection_concept_id="C1-PROV", limit=2)
        assert output["next_cursor"] is not None
        parsed = decode_cursor(output["next_cursor"])
        assert parsed["backend"] == "cmr"
        assert parsed["value"] == "tok-abc"

    def test_second_page_passes_search_after(self, monkeypatch):
        tool = _load_tool()
        cursor = encode_cursor("cmr", "tok-xyz")
        captured = {}

        def fake_search_cmr(**kwargs):
            captured[kwargs["concept_type"]] = kwargs
            if kwargs.get("concept_type") == "collection":
                yield _collection_page(["TL1-PROV", "TL2-PROV"])
            else:
                yield _tool_page()

        monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)
        tool.get_tools(collection_concept_id="C1-PROV", cursor=cursor, limit=2)
        assert captured["tool"]["search_after"] == "tok-xyz"

    def test_invalid_cursor_returns_error(self, monkeypatch):
        tool = _load_tool()
        output = tool.get_tools(collection_concept_id="C1-PROV", cursor="!!!")
        assert output["status"] == "error"
        assert "cursor" in output["error_message"].lower()
        assert output["next_cursor"] is None

    def test_cross_backend_cursor_returns_error(self, monkeypatch):
        tool = _load_tool()
        cursor = encode_cursor("kms", 10)
        output = tool.get_tools(collection_concept_id="C1-PROV", cursor=cursor)
        assert output["status"] == "error"
        assert "cursor" in output["error_message"].lower()
        assert output["next_cursor"] is None

    def test_fields_filter_returns_only_requested_fields(self, monkeypatch):
        tool = _load_tool()
        raw_item = {
            "meta": {"concept-id": "TL1-PROV"},
            "umm": {
                "Name": "Giovanni",
                "LongName": "Giovanni Online Visualization Tool",
                "Version": "1.0",
            },
        }

        def fake_search_cmr(**kwargs):
            yield _tool_page(items=[raw_item])

        monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)
        output = tool.get_tools(keyword="Giovanni", fields=["name"])
        assert output["status"] == "success"
        item = output["tools"][0]
        assert "concept_id" in item
        assert "name" in item
        assert "long_name" not in item
        assert "version" not in item
