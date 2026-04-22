"""Tests for the get_citations MCP tool."""

import importlib
import types
from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from models.tools.cmr_search import SearchStatus
from util.cmr.client import CMRError, CMRSearchResponse


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
    """Mock search_cmr across all test functions."""
    with patch("tools.get_citations.tool.search_cmr") as mock_cmr:
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
