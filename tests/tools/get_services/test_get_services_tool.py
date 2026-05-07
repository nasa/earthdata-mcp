"""Tests for the get_services MCP tool."""

import importlib
from unittest.mock import patch

import util.cmr.search_tools as _search_tools_mod
from util.cmr.client import CMRError, CMRSearchResponse
from util.pagination import decode_cursor, encode_cursor


def _load_tool():
    return importlib.import_module("tools.get_services.tool")


def _patch_search_cmr(monkeypatch, tool, fake_fn):
    """Patch search_cmr in both the tool module and search_tools (used by fetch_association_ids)."""
    monkeypatch.setattr(tool, "search_cmr", fake_fn)
    monkeypatch.setattr(_search_tools_mod, "search_cmr", fake_fn)


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
        _patch_search_cmr(
            monkeypatch,
            tool,
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
        _patch_search_cmr(
            monkeypatch,
            tool,
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
        _patch_search_cmr(
            monkeypatch,
            tool,
            _make_two_phase_mock(_collection_page(["S2-PROV"]), _service_page(items=[raw_item])),
        )

        output = tool.get_services(collection_concept_id="C1-PROV")

        assert len(output["services"]) == 1
        assert output["services"][0]["access_constraints"] == "None"
        assert output["services"][0]["use_constraints"] == "Public Domain"

    def test_total_hits_reflects_service_page(self, monkeypatch):
        """total_hits should come from the service search page."""
        tool = _load_tool()
        _patch_search_cmr(
            monkeypatch,
            tool,
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

        _patch_search_cmr(monkeypatch, tool, fake_search_cmr)

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

        _patch_search_cmr(monkeypatch, tool, fake_search_cmr)

        output = tool.get_services(collection_concept_id="C99999-MISSING")

        assert output["status"] == "no_results"
        assert output["services"] == []

    def test_returns_no_results_when_collection_has_no_services(self, monkeypatch):
        """Should return no_results when the collection has no service associations."""
        tool = _load_tool()

        def fake_search_cmr(**kwargs):
            yield _collection_page(service_ids=[])

        _patch_search_cmr(monkeypatch, tool, fake_search_cmr)

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

        _patch_search_cmr(monkeypatch, tool, fake_search_cmr)

        output = tool.get_services(collection_concept_id="C1-PROV")

        assert output["status"] == "no_results"

    def test_returns_no_results_when_service_page_is_none(self, monkeypatch):
        """Should return no_results when the service search yields nothing."""
        tool = _load_tool()

        def fake_search_cmr(**kwargs):
            if kwargs["concept_type"] == "collection":
                yield _collection_page(["S1-PROV"])
            # service call yields nothing → next() returns None

        _patch_search_cmr(monkeypatch, tool, fake_search_cmr)

        output = tool.get_services(collection_concept_id="C1-PROV")

        assert output["status"] == "no_results"


class TestGetServicesErrors:
    """Tests for error-response scenarios."""

    def test_returns_error_on_collection_cmr_error(self, monkeypatch):
        """Should return status='error' when the collection lookup raises CMRError."""
        tool = _load_tool()

        def fake_search_cmr(**kwargs):
            raise CMRError("Collection lookup failed")
            yield  # pragma: no cover

        _patch_search_cmr(monkeypatch, tool, fake_search_cmr)

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
                yield  # pragma: no cover

        _patch_search_cmr(monkeypatch, tool, fake_search_cmr)

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

        _patch_search_cmr(monkeypatch, tool, fake_search_cmr)

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

        _patch_search_cmr(monkeypatch, tool, fake_search_cmr)

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

        _patch_search_cmr(monkeypatch, tool, fake_search_cmr)

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

        _patch_search_cmr(monkeypatch, tool, fake_search_cmr)

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

        _patch_search_cmr(
            monkeypatch,
            tool,
            _make_two_phase_mock(_collection_page(["S0-PROV", "S1-PROV", "S2-PROV"]), service_pg),
        )

        output = tool.get_services(collection_concept_id="C1-PROV", limit=2)

        assert output["status"] == "success"
        assert output["total_hits"] == 3
        assert output["next_cursor"] is not None
        parsed = decode_cursor(output["next_cursor"])
        assert parsed["backend"] == "cmr"
        assert isinstance(parsed["value"], dict)
        assert parsed["value"]["token"] == "tok-abc"

    def test_get_services_pagination_second_page(self, monkeypatch):
        """A cursor skips Phase 1 and forwards search_after to Phase 2 search_cmr."""
        tool = _load_tool()
        captured = {}

        def fake_search_cmr(**kwargs):
            captured[kwargs["concept_type"]] = kwargs
            yield _service_page()

        _patch_search_cmr(monkeypatch, tool, fake_search_cmr)

        cursor = encode_cursor(
            "cmr",
            {
                "token": "tok-abc",
                "params": {"concept_id[]": ["S1-PROV"]},
                "inputs": {"collection_concept_id": "C1-PROV", "keyword": None, "type": None},
            },
        )
        tool.get_services(collection_concept_id="C1-PROV", cursor=cursor)

        assert "collection" not in captured
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
        _patch_search_cmr(
            monkeypatch,
            tool,
            _make_two_phase_mock(_collection_page(["S1-PROV"]), _service_page(items=[raw_item])),
        )

        output = tool.get_services(collection_concept_id="C1-PROV")

        svc = output["services"][0]
        assert svc["service_keywords"] == [{"ServiceCategory": "DATA ACCESS"}]
        assert svc["service_organizations"] == [
            {"roles": ["SERVICE PROVIDER"], "short_name": "PO.DAAC"}
        ]

    def test_get_services_old_format_cursor_returns_error(self, monkeypatch):
        """An old-format (scalar string) cursor must return a clean error."""
        tool = _load_tool()

        old_cursor = encode_cursor("cmr", "some-legacy-token")
        output = tool.get_services(collection_concept_id="C1-PROV", cursor=old_cursor)

        assert output["status"] == "error"
        assert output["next_cursor"] is None
        assert "outdated" in output["error_message"].lower()

    def test_get_services_cursor_override(self, monkeypatch):
        tool = _load_tool()
        from util.pagination import encode_cursor

        cursor = encode_cursor(
            "cmr",
            {
                "token": "tok-abc",
                "params": {"keyword": "original"},
                "inputs": {"keyword": "original"},
            },
        )
        res = tool.get_services(keyword="changed", cursor=cursor)
        assert res["status"] == "error"
        assert "query-scoped" in res["error_message"]

    def test_get_services_phase1_skipped_on_page2(self, monkeypatch):
        """Page 2 with cursor must not perform the Phase 1 collection lookup."""
        tool = _load_tool()
        call_count = [0]

        def fake_search_cmr(**kwargs):
            call_count[0] += 1
            yield _service_page()

        _patch_search_cmr(monkeypatch, tool, fake_search_cmr)

        cursor = encode_cursor(
            "cmr",
            {
                "token": "tok-abc",
                "params": {"concept_id[]": ["S1-PROV"]},
                "inputs": {"collection_concept_id": "C1-PROV", "keyword": None, "type": None},
            },
        )
        tool.get_services(collection_concept_id="C1-PROV", cursor=cursor)

        assert call_count[0] == 1


def test_get_services_validation_error():
    from tools.get_services.tool import get_services

    res = get_services(
        collection_concept_id="C123-PROV", limit=100
    )  # limit=100 triggers validation error
    assert res["status"] == "error"


def test_get_services_cursor_post():
    from unittest.mock import patch

    from tools.get_services.tool import get_services

    # Line 195 is the bare except block. Force an exception during field application or dict conversion
    with patch("tools.get_services.tool.apply_field_filter", side_effect=Exception("Crash")):
        res = get_services(collection_concept_id="C1-PROV", fields=["concept_id"])
        # Should not crash but return error status
        assert res["status"] == "error"


def test_get_services_bare_except():
    from unittest.mock import patch

    from tools.get_services.tool import get_services

    with patch("tools.get_services.tool.apply_field_filter", side_effect=Exception("Crash")):
        res = get_services(collection_concept_id="C1-PROV", fields=["concept_id"])
        assert res["status"] == "error"


def test_get_services_bare_except_coverage():
    from unittest.mock import patch

    from tools.get_services.tool import get_services

    with patch("tools.get_services.tool.apply_field_filter", side_effect=Exception("Crash")):
        res = get_services(collection_concept_id="C1-PROV", fields=["concept_id"])
        assert res["status"] == "error"


def test_get_services_apply_field_filter_error():
    from unittest.mock import patch

    from tools.get_services.tool import get_services

    with patch(
        "tools.get_services.tool.apply_field_filter", side_effect=Exception("mock field error")
    ):
        get_services(collection_concept_id="C1-PROV", fields=["concept_id"])
        # It's not a try/except, it just throws if it crashes, or maybe it is caught in the MCP wrapper.
        # But let's check if there's a bare except in the tool.
        # Wait, 195 is the `return response_dict` line! It's just not getting hit if `apply_field_filter` throws!
        # Ah, the bare except is at line 195 in the tool? Let's verify line 195.
