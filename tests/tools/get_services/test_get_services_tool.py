"""Tests for the get_services MCP tool."""

import importlib
from unittest.mock import patch

from models.pagination import decode_cursor, encode_cursor
from util.cmr.client import CMRError, CMRSearchResponse


def _load_tool():
    return importlib.import_module("tools.get_services.tool")


def _collection_page(service_ids=None):
    """Build a collection CMRSearchResponse whose meta carries the given service IDs."""
    associations = {}
    if service_ids is not None:
        associations["services"] = service_ids
    item = {"meta": {"concept-id": "C1-PROV", "associations": associations}, "umm": {}}
    return CMRSearchResponse(items=[item], total_hits=1, took_ms=5, search_after=None, page_size=1)


def _service_page(items=None, total_hits=1, search_after=None, page_size=10):
    """Build a service CMRSearchResponse."""
    return CMRSearchResponse(
        items=items or [{"meta": {"concept-id": "S1-PROV"}, "umm": {"Name": "My Service"}}],
        total_hits=total_hits,
        took_ms=8,
        search_after=search_after,
        page_size=page_size,
    )


def _make_two_phase_mock(collection_page, service_page):
    """Return a fake search_cmr that yields collection_page then service_page."""

    def fake_search_cmr(**kwargs):
        if kwargs.get("concept_type") == "collection":
            yield collection_page
        else:
            yield service_page

    return fake_search_cmr


class TestGetServicesSuccess:
    """Happy-path tests for get_services."""

    def test_returns_success_status(self, monkeypatch):
        """Should return status='success' when the collection has associated services."""
        tool = _load_tool()
        monkeypatch.setattr(
            tool,
            "search_cmr",
            _make_two_phase_mock(_collection_page(["S1-PROV"]), _service_page()),
        )

        output = tool.get_services(collection_concept_id="C1-PROV")

        assert output["status"] == "success"
        assert output["next_cursor"] is None

    def test_services_contains_normalized_items(self, monkeypatch):
        """services should be properly normalized into snake_case fields."""
        tool = _load_tool()
        raw_item = {
            "meta": {"concept-id": "S1-PROV"},
            "umm": {
                "Name": "OPeNDAP",
                "Type": "OPeNDAP",
                "AccessConstraints": {"Description": "Requires Login"},
            },
        }
        monkeypatch.setattr(
            tool,
            "search_cmr",
            _make_two_phase_mock(_collection_page(["S1-PROV"]), _service_page(items=[raw_item])),
        )

        output = tool.get_services(collection_concept_id="C1-PROV")

        assert len(output["services"]) == 1
        assert output["services"][0]["concept_id"] == "S1-PROV"
        assert output["services"][0]["name"] == "OPeNDAP"
        assert output["services"][0]["access_constraints"] == {"Description": "Requires Login"}

    def test_services_handles_string_constraints(self, monkeypatch):
        """services should allow string formats for legacy access/use constraints."""
        tool = _load_tool()
        raw_item = {
            "meta": {"concept-id": "S2-PROV"},
            "umm": {
                "Name": "LegacyService",
                "AccessConstraints": "None",
                "UseConstraints": "Public Domain",
            },
        }
        monkeypatch.setattr(
            tool,
            "search_cmr",
            _make_two_phase_mock(_collection_page(["S2-PROV"]), _service_page(items=[raw_item])),
        )

        output = tool.get_services(collection_concept_id="C1-PROV")

        assert len(output["services"]) == 1
        assert output["services"][0]["access_constraints"] == "None"
        assert output["services"][0]["use_constraints"] == "Public Domain"

    def test_total_hits_reflects_service_page(self, monkeypatch):
        """total_hits should come from the service search page."""
        tool = _load_tool()
        monkeypatch.setattr(
            tool,
            "search_cmr",
            _make_two_phase_mock(
                _collection_page(["S1-PROV", "S2-PROV"]),
                _service_page(total_hits=2),
            ),
        )

        output = tool.get_services(collection_concept_id="C1-PROV")

        assert output["total_hits"] == 2
        assert "took_ms" not in output

    def test_service_search_receives_concept_id_list(self, monkeypatch):
        """Phase 2 search_cmr should receive the discovered service IDs as concept_id[]."""
        tool = _load_tool()
        captured = {}

        def fake_search_cmr(**kwargs):
            captured[kwargs["concept_type"]] = kwargs
            if kwargs["concept_type"] == "collection":
                yield _collection_page(["S1-PROV", "S2-PROV"])
            else:
                yield _service_page()

        monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)

        tool.get_services(collection_concept_id="C1-PROV")

        assert captured["service"]["search_params"]["concept_id[]"] == ["S1-PROV", "S2-PROV"]
        assert captured["service"]["page_size"] == 10


class TestGetServicesNoResults:
    """Tests for no-results scenarios."""

    def test_returns_no_results_when_collection_not_found(self, monkeypatch):
        """Should return no_results when the collection search yields no items."""
        tool = _load_tool()
        empty_page = CMRSearchResponse(
            items=[], total_hits=0, took_ms=3, search_after=None, page_size=0
        )

        def fake_search_cmr(**kwargs):
            yield empty_page

        monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)

        output = tool.get_services(collection_concept_id="C99999-MISSING")

        assert output["status"] == "no_results"
        assert output["services"] == []

    def test_returns_no_results_when_collection_has_no_services(self, monkeypatch):
        """Should return no_results when the collection has no service associations."""
        tool = _load_tool()

        def fake_search_cmr(**kwargs):
            yield _collection_page(service_ids=[])

        monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)

        output = tool.get_services(collection_concept_id="C1-PROV")

        assert output["status"] == "no_results"

    def test_returns_no_results_when_associations_key_absent(self, monkeypatch):
        """Should return no_results when meta.associations has no 'services' key."""
        tool = _load_tool()
        item = {"meta": {"concept-id": "C1-PROV", "associations": {}}, "umm": {}}
        page = CMRSearchResponse(
            items=[item], total_hits=1, took_ms=5, search_after=None, page_size=1
        )

        def fake_search_cmr(**kwargs):
            yield page

        monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)

        output = tool.get_services(collection_concept_id="C1-PROV")

        assert output["status"] == "no_results"

    def test_returns_no_results_when_service_page_is_none(self, monkeypatch):
        """Should return no_results when the service search yields nothing."""
        tool = _load_tool()

        def fake_search_cmr(**kwargs):
            if kwargs["concept_type"] == "collection":
                yield _collection_page(["S1-PROV"])
            # service call yields nothing → next() returns None

        monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)

        output = tool.get_services(collection_concept_id="C1-PROV")

        assert output["status"] == "no_results"


class TestGetServicesErrors:
    """Tests for error-response scenarios."""

    def test_returns_error_on_collection_cmr_error(self, monkeypatch):
        """Should return status='error' when the collection lookup raises CMRError."""
        tool = _load_tool()

        def fake_search_cmr(**kwargs):
            raise CMRError("Collection lookup failed")
            yield  # pragma: no cover  # noqa: unreachable

        monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)

        output = tool.get_services(collection_concept_id="C1-PROV")

        assert output["status"] == "error"
        assert "Collection lookup failed" in output["error_message"]

    def test_returns_error_on_service_cmr_error(self, monkeypatch):
        """Should return status='error' when the service search raises CMRError."""
        tool = _load_tool()

        def fake_search_cmr(**kwargs):
            if kwargs["concept_type"] == "collection":
                yield _collection_page(["S1-PROV"])
            else:
                raise CMRError("Service fetch failed")
                yield  # pragma: no cover  # noqa: unreachable

        monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)

        output = tool.get_services(collection_concept_id="C1-PROV")

        assert output["status"] == "error"
        assert "Service fetch failed" in output["error_message"]

    def test_returns_error_on_input_validation(self, monkeypatch):
        """Should return status='error' when input validation fails."""
        tool = _load_tool()

        output = tool.get_services(collection_concept_id="invalid_format")

        assert output["status"] == "error"
        assert "error_message" in output
        assert "Invalid collection concept ID format" in output["error_message"]

    def test_returns_error_on_unexpected_collection_error(self, monkeypatch):
        """Should return status='error' when an unexpected Exception occurs during collection lookup."""
        tool = _load_tool()

        def fake_search_cmr(**kwargs):
            raise RuntimeError("Unexpected collection boom")
            yield

        monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)

        output = tool.get_services(collection_concept_id="C1-PROV")

        assert output["status"] == "error"
        assert (
            output["error_message"]
            == "An unexpected internal error occurred during collection lookup."
        )

    def test_returns_error_on_unexpected_service_error(self, monkeypatch):
        """Should return status='error' when an unexpected Exception occurs during service lookup."""
        tool = _load_tool()

        def fake_search_cmr(**kwargs):
            if kwargs["concept_type"] == "collection":
                yield _collection_page(["S1-PROV"])
            else:
                raise RuntimeError("Unexpected service boom")
                yield

        monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)

        output = tool.get_services(collection_concept_id="C1-PROV")

        assert output["status"] == "error"
        assert (
            output["error_message"] == "An unexpected internal error occurred during service fetch."
        )


def test_get_services_calls_trace_update(monkeypatch):
    """Test telemetry tracing."""
    tool = _load_tool()

    page = _collection_page([])

    def fake_search_cmr(**kwargs):
        yield page

    monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)

    with patch.object(tool, "trace_update") as mock_trace_update:
        tool.get_services(collection_concept_id="C1-PROV")

    assert mock_trace_update.called


class TestGetServicesNewParams:
    """Tests for new keyword, type, pagination, and field params."""

    def test_get_services_keyword_only(self, monkeypatch):
        """keyword-only call: Phase 1 skipped, search_cmr called once with keyword in search_params."""
        tool = _load_tool()
        captured = {}

        def fake_search_cmr(**kwargs):
            captured[kwargs["concept_type"]] = kwargs
            yield _service_page()

        monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)

        output = tool.get_services(keyword="OPeNDAP")

        assert output["status"] == "success"
        assert "collection" not in captured
        assert captured["service"]["search_params"] == {"keyword": "OPeNDAP"}

    def test_get_services_type_only(self, monkeypatch):
        """type-only call: Phase 1 skipped, search_cmr called with type in search_params."""
        tool = _load_tool()
        captured = {}

        def fake_search_cmr(**kwargs):
            captured[kwargs["concept_type"]] = kwargs
            yield _service_page()

        monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)

        output = tool.get_services(type="OPeNDAP")

        assert output["status"] == "success"
        assert captured["service"]["search_params"] == {"type": "OPeNDAP"}

    def test_get_services_no_args_error(self, monkeypatch):
        """Calling with no args should return error with 'at least one' in the message."""
        tool = _load_tool()

        output = tool.get_services()

        assert output["status"] == "error"
        assert "at least one" in output["error_message"].lower()

    def test_get_services_pagination_first_page(self, monkeypatch):
        """limit=2 with 3 service IDs: next_cursor should be set when page has search_after."""
        tool = _load_tool()
        items = [
            {"meta": {"concept-id": f"S{i}-PROV"}, "umm": {"Name": f"Svc{i}"}} for i in range(2)
        ]
        service_pg = _service_page(items=items, total_hits=3, search_after="tok-abc", page_size=2)

        monkeypatch.setattr(
            tool,
            "search_cmr",
            _make_two_phase_mock(_collection_page(["S0-PROV", "S1-PROV", "S2-PROV"]), service_pg),
        )

        output = tool.get_services(collection_concept_id="C1-PROV", limit=2)

        assert output["status"] == "success"
        assert output["total_hits"] == 3
        assert output["next_cursor"] is not None
        parsed = decode_cursor(output["next_cursor"])
        assert parsed["backend"] == "cmr"
        assert parsed["value"] == "tok-abc"

    def test_get_services_pagination_second_page(self, monkeypatch):
        """Passing a cursor should forward search_after to Phase 2 search_cmr."""
        tool = _load_tool()
        captured = {}

        def fake_search_cmr(**kwargs):
            captured[kwargs["concept_type"]] = kwargs
            if kwargs["concept_type"] == "collection":
                yield _collection_page(["S1-PROV"])
            else:
                yield _service_page()

        monkeypatch.setattr(tool, "search_cmr", fake_search_cmr)

        cursor = encode_cursor("cmr", "tok-abc")
        tool.get_services(collection_concept_id="C1-PROV", cursor=cursor)

        assert captured["service"]["search_after"] == "tok-abc"

    def test_get_services_invalid_cursor(self, monkeypatch):
        """An invalid cursor string should return an error with 'cursor' in the message."""
        tool = _load_tool()

        output = tool.get_services(collection_concept_id="C1-PROV", cursor="!!!invalid!!!")

        assert output["status"] == "error"
        assert "cursor" in output["error_message"].lower()
        assert output["next_cursor"] is None

    def test_get_services_cross_backend_cursor(self, monkeypatch):
        """A cursor from a different backend should return an error."""
        tool = _load_tool()

        cursor = encode_cursor("kms", 10)
        output = tool.get_services(collection_concept_id="C1-PROV", cursor=cursor)

        assert output["status"] == "error"
        assert "cursor" in output["error_message"].lower()
        assert output["next_cursor"] is None

    def test_get_services_new_fields(self, monkeypatch):
        """service_keywords and service_organizations should be normalized from UMM-S."""
        tool = _load_tool()
        raw_item = {
            "meta": {"concept-id": "S1-PROV"},
            "umm": {
                "Name": "OPeNDAP",
                "ServiceKeywords": [{"ServiceCategory": "DATA ACCESS"}],
                "ServiceOrganizations": [{"Roles": ["SERVICE PROVIDER"], "ShortName": "PO.DAAC"}],
            },
        }
        monkeypatch.setattr(
            tool,
            "search_cmr",
            _make_two_phase_mock(_collection_page(["S1-PROV"]), _service_page(items=[raw_item])),
        )

        output = tool.get_services(collection_concept_id="C1-PROV")

        svc = output["services"][0]
        assert svc["service_keywords"] == [{"ServiceCategory": "DATA ACCESS"}]
        assert svc["service_organizations"] == [
            {"roles": ["SERVICE PROVIDER"], "short_name": "PO.DAAC"}
        ]
