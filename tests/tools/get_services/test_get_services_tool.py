"""Tests for the get_services MCP tool."""

import importlib

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
        assert captured["service"]["page_size"] == 2000


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
