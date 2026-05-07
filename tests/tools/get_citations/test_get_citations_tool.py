"""Tests for the get_citations MCP tool."""

import importlib
import types
from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from models.tools.cmr_search import SearchStatus
from util.cmr.client import CMRError, CMRSearchResponse
from util.pagination import decode_cursor, encode_cursor


def _load_tool() -> types.ModuleType:
    return importlib.import_module("tools.get_citations.tool")


def _collection_page(citation_ids: list[str] | None = None) -> CMRSearchResponse:
    """Build a collection CMRSearchResponse whose meta carries the given citation IDs."""
    associations = {}
    if citation_ids is not None:
        associations["citations"] = citation_ids
    item = {"meta": {"concept-id": "C1-PROV", "associations": associations}, "umm": {}}
    return CMRSearchResponse(items=[item], total_hits=1, took_ms=5, search_after=None, page_size=1)


def _citation_page(
    items: list[dict[str, Any]] | None = None,
    total_hits: int = 1,
    search_after: str | None = None,
    page_size: int = 10,
) -> CMRSearchResponse:
    """Build a citation CMRSearchResponse."""
    return CMRSearchResponse(
        items=items
        or [
            {
                "meta": {"concept-id": "CIT1-PROV"},
                "umm": {"Name": "My Citation", "Identifier": "10.1234/test"},
            }
        ],
        total_hits=total_hits,
        took_ms=8,
        search_after=search_after,
        page_size=page_size,
    )


@pytest.fixture
def mock_search_cmr() -> Generator[MagicMock]:
    """Mock search_cmr in both the tool module and search_tools (used by fetch_association_ids)."""
    with (
        patch("tools.get_citations.tool.search_cmr") as mock_cmr,
        patch("util.cmr.search_tools.search_cmr", mock_cmr),
    ):
        yield mock_cmr


def test_get_citations_invalid_input() -> None:
    """Test validation errors for get_citations."""
    tool = _load_tool()

    # Missing both
    res = tool.get_citations()
    assert res["status"] == SearchStatus.ERROR
    assert "exactly one" in res["error_message"]

    # Provide both
    res = tool.get_citations(collection_concept_id="C12345-PROV", identifier="10.x/test")
    assert res["status"] == SearchStatus.ERROR
    assert "exactly one" in res["error_message"]

    # Invalid collection ID format
    res = tool.get_citations(collection_concept_id="INVALID")
    assert res["status"] == SearchStatus.ERROR
    assert "Invalid collection concept ID format" in res["error_message"]


def test_get_citations_collection_flow_success(mock_search_cmr: MagicMock) -> None:
    """Test standard collection flow returning citations."""
    tool = _load_tool()

    # Setup mock to return collection page first, then citation page
    mock_search_cmr.side_effect = [
        iter([_collection_page(citation_ids=["CIT1-PROV", "CIT2-PROV"])]),
        iter([_citation_page()]),
    ]

    res = tool.get_citations(collection_concept_id="C123-PROV")
    assert res["status"] == SearchStatus.SUCCESS
    assert res["total_hits"] == 2
    assert len(res["citations"]) == 1
    assert res["next_cursor"] is None

    # Assert collection lookup was correct
    call1 = mock_search_cmr.call_args_list[0]
    assert call1.kwargs["concept_type"] == "collection"
    assert call1.kwargs["search_params"] == {"concept_id": "C123-PROV"}

    # Assert citation lookup used the IDs
    call2 = mock_search_cmr.call_args_list[1]
    assert call2.kwargs["concept_type"] == "citation"
    assert call2.kwargs["search_params"] == {"concept_id[]": ["CIT1-PROV", "CIT2-PROV"]}


def test_get_citations_identifier_flow_success(mock_search_cmr: MagicMock) -> None:
    """Test direct identifier lookup."""
    tool = _load_tool()

    mock_search_cmr.side_effect = [
        iter([_citation_page()]),
    ]

    res = tool.get_citations(identifier="10.1234/test")
    assert res["status"] == SearchStatus.SUCCESS
    assert res["total_hits"] == 1

    call = mock_search_cmr.call_args_list[0]
    assert call.kwargs["concept_type"] == "citation"
    assert call.kwargs["search_params"] == {"identifier": "10.1234/test"}


def test_get_citations_no_associations(mock_search_cmr: MagicMock) -> None:
    """Test collection flow where collection has no citations."""
    tool = _load_tool()

    # Collection returns but has no citations
    mock_search_cmr.side_effect = [
        iter([_collection_page(citation_ids=[])]),
    ]

    res = tool.get_citations(collection_concept_id="C123-PROV")
    assert res["status"] == SearchStatus.NO_RESULTS


def test_get_citations_collection_not_found(mock_search_cmr: MagicMock) -> None:
    """Test collection flow where collection doesn't exist."""
    tool = _load_tool()

    # Collection lookup yields nothing
    mock_search_cmr.side_effect = [iter([])]

    res = tool.get_citations(collection_concept_id="C123-PROV")
    assert res["status"] == SearchStatus.NO_RESULTS


def test_get_citations_collection_error(mock_search_cmr: MagicMock) -> None:
    """Test collection flow where CMR API errors out."""
    tool = _load_tool()

    mock_search_cmr.side_effect = CMRError("CMR is down")

    res = tool.get_citations(collection_concept_id="C123-PROV")
    assert res["status"] == SearchStatus.ERROR
    assert "CMR is down" in res["error_message"]


def test_get_citations_citation_fetch_error(mock_search_cmr: MagicMock) -> None:
    """Test collection flow where citation fetch errors out."""
    tool = _load_tool()

    mock_search_cmr.side_effect = [
        iter([_collection_page(citation_ids=["CIT1-PROV"])]),
        CMRError("CMR citations down"),
    ]

    res = tool.get_citations(collection_concept_id="C123-PROV")
    assert res["status"] == SearchStatus.ERROR
    assert "CMR citations down" in res["error_message"]


def test_get_citations_no_citations_returned(mock_search_cmr: MagicMock) -> None:
    """Test where citation search yields no results despite having IDs."""
    tool = _load_tool()

    mock_search_cmr.side_effect = [
        iter([_collection_page(citation_ids=["CIT1-PROV"])]),
        iter([]),  # Citation lookup yields nothing
    ]

    res = tool.get_citations(collection_concept_id="C123-PROV")
    assert res["status"] == SearchStatus.NO_RESULTS


def test_get_citations_generic_exception(mock_search_cmr: MagicMock) -> None:
    """Test generic unhandled exceptions."""
    tool = _load_tool()

    mock_search_cmr.side_effect = [RuntimeError("Unexpected internal crash")]
    res = tool.get_citations(collection_concept_id="C123-PROV")
    assert res["status"] == SearchStatus.ERROR
    assert "unexpected internal error" in res["error_message"]

    mock_search_cmr.side_effect = [
        iter([_collection_page(citation_ids=["CIT1-PROV"])]),
        RuntimeError("Unexpected internal crash 2"),
    ]
    res = tool.get_citations(collection_concept_id="C123-PROV")
    assert res["status"] == SearchStatus.ERROR
    assert "unexpected internal error" in res["error_message"]


def test_get_citations_calls_trace_update(mock_search_cmr: MagicMock) -> None:
    """Test telemetry tracing."""
    tool = _load_tool()

    mock_search_cmr.side_effect = [iter([_citation_page()])]

    with patch.object(tool, "trace_update") as mock_trace_update:
        tool.get_citations(identifier="10.1234/test")

    assert mock_trace_update.called


def test_get_citations_next_cursor_present(mock_search_cmr: MagicMock) -> None:
    """Test that next_cursor is set when page is full and search_after is present."""
    tool = _load_tool()

    two_items = [
        {
            "meta": {"concept-id": f"CIT{i}-PROV"},
            "umm": {"Name": f"Cite {i}", "Identifier": f"10./{i}"},
        }
        for i in range(2)
    ]
    mock_search_cmr.side_effect = [
        iter([_collection_page(citation_ids=["CIT0-PROV", "CIT1-PROV", "CIT2-PROV"])]),
        iter([_citation_page(items=two_items, total_hits=3, search_after="tok-abc", page_size=2)]),
    ]

    res = tool.get_citations(collection_concept_id="C123-PROV", limit=2)
    assert res["next_cursor"] is not None
    parsed = decode_cursor(res["next_cursor"])
    assert parsed["backend"] == "cmr"
    assert isinstance(parsed["value"], dict)
    assert parsed["value"]["token"] == "tok-abc"


def test_get_citations_cursor_advances_page(mock_search_cmr: MagicMock) -> None:
    """A valid cursor causes Phase 1 to be skipped and Phase 2 to receive search_after."""
    tool = _load_tool()

    cursor = encode_cursor(
        "cmr",
        {
            "token": "tok-xyz",
            "params": {"concept_id[]": ["CIT1-PROV"]},
            "inputs": {"collection_concept_id": "C123-PROV"},
        },
    )

    mock_search_cmr.side_effect = [iter([_citation_page()])]

    tool.get_citations(collection_concept_id="C123-PROV", cursor=cursor)

    assert mock_search_cmr.call_count == 1
    call1 = mock_search_cmr.call_args_list[0]
    assert call1.kwargs["search_after"] == "tok-xyz"


def test_get_citations_fields_filter(mock_search_cmr: MagicMock) -> None:
    """Test that fields filtering removes non-requested keys while keeping concept_id."""
    tool = _load_tool()

    mock_search_cmr.side_effect = [iter([_citation_page()])]

    res = tool.get_citations(identifier="10.1234/test", fields=["name"])
    assert res["status"] == "success"
    item = res["citations"][0]
    assert "concept_id" in item
    assert "name" in item
    assert "identifier" not in item
    assert "abstract" not in item


def test_get_citations_provider_filter(mock_search_cmr: MagicMock) -> None:
    """Test that provider is passed to the Phase 2 citation search."""
    tool = _load_tool()

    mock_search_cmr.side_effect = [
        iter([_collection_page(citation_ids=["CIT1-PROV"])]),
        iter([_citation_page()]),
    ]

    tool.get_citations(collection_concept_id="C123-PROV", provider="ESDIS")

    call2 = mock_search_cmr.call_args_list[1]
    assert call2.kwargs["search_params"].get("provider") == "ESDIS"


def test_get_citations_provider_identifier_flow(mock_search_cmr: MagicMock) -> None:
    """Test that provider is passed through in the direct identifier flow."""
    tool = _load_tool()

    mock_search_cmr.side_effect = [iter([_citation_page()])]

    tool.get_citations(identifier="10.1234/test", provider="ESDIS")

    call = mock_search_cmr.call_args_list[0]
    assert call.kwargs["search_params"].get("provider") == "ESDIS"


def test_get_citations_invalid_cursor(mock_search_cmr: MagicMock) -> None:  # pylint: disable=unused-argument
    """Test that an invalid cursor returns an error."""
    tool = _load_tool()

    res = tool.get_citations(collection_concept_id="C123-PROV", cursor="not-valid-base64!!!")
    assert res["status"] == SearchStatus.ERROR
    assert "cursor" in res["error_message"].lower()
    assert res["next_cursor"] is None


def test_get_citations_cross_backend_cursor(mock_search_cmr: MagicMock) -> None:  # pylint: disable=unused-argument
    """Test that a cursor from a different backend returns an error."""
    tool = _load_tool()

    cursor = encode_cursor("kms", 10)
    res = tool.get_citations(collection_concept_id="C123-PROV", cursor=cursor)
    assert res["status"] == SearchStatus.ERROR
    assert "cursor" in res["error_message"].lower()
    assert res["next_cursor"] is None


def test_get_citations_old_format_cursor_returns_error(mock_search_cmr: MagicMock) -> None:  # pylint: disable=unused-argument
    """An old-format (scalar string) cursor must return a clean error."""
    tool = _load_tool()

    old_cursor = encode_cursor("cmr", "some-legacy-token")
    res = tool.get_citations(collection_concept_id="C123-PROV", cursor=old_cursor)

    assert res["status"] == SearchStatus.ERROR
    assert res["next_cursor"] is None
    assert "outdated" in res["error_message"].lower()


def test_get_citations_cursor_override():
    """Ensure changing query parameters on page 2 rejects the cursor."""
    from tools.get_citations.tool import get_citations

    cursor = encode_cursor(
        "cmr",
        {
            "token": "tok-abc",
            "params": {"identifier": "10.original/test"},
            "inputs": {"identifier": "10.original/test"},
        },
    )
    res = get_citations(identifier="10.changed/test", cursor=cursor)
    assert res["status"] == "error"
    assert "query-scoped" in res["error_message"]


def test_get_citations_phase1_skipped_on_page2(mock_search_cmr: MagicMock) -> None:
    """Page 2 with cursor must not perform the Phase 1 collection lookup."""
    tool = _load_tool()
    mock_search_cmr.side_effect = [iter([_citation_page()])]

    cursor = encode_cursor(
        "cmr",
        {
            "token": "tok-abc",
            "params": {"concept_id[]": ["CIT1-PROV"]},
            "inputs": {"collection_concept_id": "C123-PROV"},
        },
    )
    tool.get_citations(collection_concept_id="C123-PROV", cursor=cursor)

    assert mock_search_cmr.call_count == 1
    assert mock_search_cmr.call_args_list[0].kwargs["concept_type"] == "citation"


def test_get_citations_total_hits_on_page2(mock_search_cmr: MagicMock) -> None:
    """total_hits on page 2 must come from the citation page, not len(citation_ids)."""
    tool = _load_tool()
    mock_search_cmr.side_effect = [iter([_citation_page(total_hits=42)])]

    cursor = encode_cursor(
        "cmr",
        {
            "token": "tok-abc",
            "params": {"concept_id[]": ["CIT1-PROV"]},
            "inputs": {"collection_concept_id": "C123-PROV"},
        },
    )
    res = tool.get_citations(collection_concept_id="C123-PROV", cursor=cursor)

    assert res["total_hits"] == 42


def test_get_citations_validation_error():
    """Test validation error for get_citations."""
    from tools.get_citations.tool import get_citations

    res = get_citations(
        collection_concept_id="C123", limit=100
    )  # limit=100 triggers validation error
    assert res["status"] == "error"


def test_get_citations_model_validation_errors():
    """Test model validation errors for get_citations."""
    from tools.get_citations.tool import get_citations

    # Test exactly one of identifier/concept_id error
    res1 = get_citations(collection_concept_id="C1-PROV", identifier="10.123/456")
    assert res1["status"] == "error"
    assert "exactly one" in res1["error_message"]

    # Test invalid concept id
    res2 = get_citations(collection_concept_id="INVALID")
    assert res2["status"] == "error"
    assert "Invalid collection concept ID format" in res2["error_message"]


def test_get_citations_validation_error2():
    """Test another validation error for get_citations."""
    from tools.get_citations.tool import get_citations

    res = get_citations(collection_concept_id="C1-PROV", identifier="10.123/456")
    assert res["status"] == "error"


def test_get_citations_validation_error_empty():
    """Test empty string validation error for get_citations."""
    from tools.get_citations.tool import get_citations

    res = get_citations(collection_concept_id="")
    assert res["status"] == "error"
    res2 = get_citations(identifier="")
    assert res2["status"] == "error"
