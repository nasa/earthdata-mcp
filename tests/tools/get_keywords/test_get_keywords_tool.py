"""Tests for the get_keywords MCP tool."""

import importlib
import types
from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
import requests
from fastmcp.exceptions import ToolError

from models.tools.cmr_search import SearchStatus
from util.pagination import decode_cursor, encode_cursor


def _load_tool() -> types.ModuleType:
    """Load the tool module dynamically to avoid circular imports."""
    return importlib.import_module("tools.get_keywords.tool")


@pytest.fixture
def mock_search_kms_pattern() -> Generator[MagicMock]:
    """Mock util.kms.client.search_kms_pattern."""
    with patch("tools.get_keywords.tool.search_kms_pattern") as mock_search:
        yield mock_search


def test_get_keywords_global_success(mock_search_kms_pattern: MagicMock) -> None:
    """Test successful global keyword search."""
    tool = _load_tool()

    mock_search_kms_pattern.return_value = [
        {
            "uuid": "test-uuid-1",
            "prefLabel": "MODIS",
            "scheme": {"shortName": "instruments", "longName": "Instruments"},
            "definitions": [{"text": "A very cool instrument."}],
        }
    ]

    result = tool.get_keywords(query="MODIS")

    assert result["status"] == SearchStatus.SUCCESS
    assert result["total_hits"] == 1
    assert len(result["keywords"]) == 1

    kw = result["keywords"][0]
    assert kw["uuid"] == "test-uuid-1"
    assert kw["prefLabel"] == "MODIS"
    assert kw["definition"] == "A very cool instrument."
    assert kw["scheme"]["shortName"] == "instruments"

    assert result["next_cursor"] is None
    mock_search_kms_pattern.assert_called_once_with("MODIS", None)


def test_get_keywords_scheme_specific_success(mock_search_kms_pattern: MagicMock) -> None:
    """Test successful scheme-specific keyword search."""
    tool = _load_tool()

    mock_search_kms_pattern.return_value = [
        {
            "uuid": "test-uuid-2",
            "prefLabel": "ATMOSPHERIC WATER VAPOR",
            "scheme": {"shortName": "sciencekeywords", "longName": "Science Keywords"},
            "definitions": [],
        }
    ]

    result = tool.get_keywords(query="WATER", scheme="sciencekeywords")

    assert result["status"] == SearchStatus.SUCCESS
    assert result["total_hits"] == 1
    assert len(result["keywords"]) == 1

    kw = result["keywords"][0]
    assert kw["uuid"] == "test-uuid-2"
    assert kw["prefLabel"] == "ATMOSPHERIC WATER VAPOR"
    assert kw["definition"] is None
    assert kw["scheme"]["shortName"] == "sciencekeywords"

    mock_search_kms_pattern.assert_called_once_with("WATER", "sciencekeywords")


def test_get_keywords_no_results(mock_search_kms_pattern: MagicMock) -> None:
    """Test behavior when no keywords match the pattern (client returns [])."""
    tool = _load_tool()

    mock_search_kms_pattern.return_value = []

    result = tool.get_keywords(query="NONEXISTENT_TERM")

    assert result["status"] == SearchStatus.NO_RESULTS
    assert result["total_hits"] == 0
    assert len(result["keywords"]) == 0
    assert result["error_message"] is None


def test_get_keywords_api_error(mock_search_kms_pattern: MagicMock) -> None:
    """Test behavior when the KMS API throws an exception."""
    tool = _load_tool()

    mock_search_kms_pattern.side_effect = requests.RequestException("Connection Timeout")

    with pytest.raises(ToolError) as exc_info:
        tool.get_keywords(query="ERROR_TERM")

    assert "Failed to communicate with KMS API" in str(exc_info.value)


def test_get_keywords_malformed_response_types(mock_search_kms_pattern: MagicMock) -> None:
    """Test behavior when the KMS API returns unexpected types for scheme or definitions."""
    tool = _load_tool()

    mock_search_kms_pattern.return_value = [
        {
            "uuid": "test-uuid-3",
            "prefLabel": "BAD DATA",
            "scheme": None,  # Should default to {}
            "definitions": ["This is a string, not a dict", 123],  # Should fail isinstance(dict)
        }
    ]

    result = tool.get_keywords(query="BAD DATA")

    assert result["status"] == SearchStatus.SUCCESS
    assert result["total_hits"] == 1
    assert len(result["keywords"]) == 1

    kw = result["keywords"][0]
    assert kw["uuid"] == "test-uuid-3"
    assert kw["prefLabel"] == "BAD DATA"
    assert kw["definition"] is None  # Because definitions[0] wasn't a dict
    assert kw["scheme"] == {}  # Because scheme wasn't a dict


def test_get_keywords_unexpected_error(mock_search_kms_pattern):
    """Test behavior on generic unexpected exception."""
    tool = _load_tool()
    mock_search_kms_pattern.side_effect = RuntimeError("Boom")

    with pytest.raises(ToolError) as exc_info:
        tool.get_keywords(query="TEST")

    assert "unexpected error" in str(exc_info.value).lower()


def test_get_keywords_calls_trace_update(mock_search_kms_pattern):
    """Test telemetry tracing."""
    tool = _load_tool()
    mock_search_kms_pattern.return_value = []

    with patch.object(tool, "trace_update") as mock_trace_update:
        tool.get_keywords(query="TEST")

    assert mock_trace_update.called


def _make_concept(n: int) -> dict:
    return {
        "uuid": f"uuid-{n}",
        "prefLabel": f"KEYWORD {n}",
        "scheme": {"shortName": "sciencekeywords"},
        "definitions": [],
    }


def test_get_keywords_pagination_first_page(mock_search_kms_pattern: MagicMock) -> None:
    """First page returns limit items, next_cursor is set, total_hits is full count."""
    tool = _load_tool()
    all_concepts = [_make_concept(i) for i in range(15)]
    mock_search_kms_pattern.return_value = all_concepts

    result = tool.get_keywords(query="KEYWORD", limit=10)

    assert result["status"] == SearchStatus.SUCCESS
    assert result["total_hits"] == 15
    assert len(result["keywords"]) == 10
    assert result["keywords"][0]["prefLabel"] == "KEYWORD 0"
    assert result["keywords"][9]["prefLabel"] == "KEYWORD 9"
    assert result["next_cursor"] is not None
    parsed = decode_cursor(result["next_cursor"])
    assert parsed["backend"] == "kms"
    assert isinstance(parsed["value"], dict)
    assert parsed["value"]["offset"] == 10
    assert parsed["value"]["query"] == "KEYWORD"


def test_get_keywords_pagination_second_page(mock_search_kms_pattern: MagicMock) -> None:
    """Second page returns remaining items, next_cursor is None."""
    tool = _load_tool()
    all_concepts = [_make_concept(i) for i in range(15)]
    mock_search_kms_pattern.return_value = all_concepts

    cursor = encode_cursor("kms", {"offset": 10, "query": "KEYWORD", "scheme": None})
    result = tool.get_keywords(query="KEYWORD", limit=10, cursor=cursor)

    assert result["status"] == SearchStatus.SUCCESS
    assert result["total_hits"] == 15
    assert len(result["keywords"]) == 5
    assert result["keywords"][0]["prefLabel"] == "KEYWORD 10"
    assert result["keywords"][4]["prefLabel"] == "KEYWORD 14"
    assert result["next_cursor"] is None


def test_get_keywords_pagination_exact_multiple(mock_search_kms_pattern: MagicMock) -> None:
    """When total is exact multiple of limit, final page has next_cursor=None."""
    tool = _load_tool()
    all_concepts = [_make_concept(i) for i in range(10)]
    mock_search_kms_pattern.return_value = all_concepts

    cursor = encode_cursor("kms", {"offset": 10, "query": "KEYWORD", "scheme": None})
    result = tool.get_keywords(query="KEYWORD", limit=10, cursor=cursor)

    assert result["status"] == SearchStatus.SUCCESS
    assert result["total_hits"] == 10
    assert len(result["keywords"]) == 0
    assert result["next_cursor"] is None


def test_get_keywords_invalid_cursor(mock_search_kms_pattern: MagicMock) -> None:
    """Garbage cursor raises a clean ToolError, not an unhandled exception."""
    tool = _load_tool()
    mock_search_kms_pattern.return_value = [_make_concept(0)]

    with pytest.raises(ToolError) as exc_info:
        tool.get_keywords(query="KEYWORD", cursor="not-valid-base64!!!")

    assert "cursor" in str(exc_info.value).lower()


def test_get_keywords_cross_backend_cursor(mock_search_kms_pattern: MagicMock) -> None:
    """A CMR cursor passed to get_keywords raises a clean ToolError, not an exception."""
    tool = _load_tool()
    mock_search_kms_pattern.return_value = [_make_concept(0)]

    cmr_cursor = encode_cursor("cmr", "some-cmr-token")

    with pytest.raises(ToolError) as exc_info:
        tool.get_keywords(query="KEYWORD", cursor=cmr_cursor)

    assert "cursor" in str(exc_info.value).lower()


def test_get_keywords_old_format_cursor_returns_error(mock_search_kms_pattern: MagicMock) -> None:
    """An old-format (scalar int) cursor must raise a clean ToolError."""
    tool = _load_tool()
    mock_search_kms_pattern.return_value = [_make_concept(0)]

    old_cursor = encode_cursor("kms", 10)

    with pytest.raises(ToolError) as exc_info:
        tool.get_keywords(query="KEYWORD", cursor=old_cursor)

    assert "cursor" in str(exc_info.value).lower()


def test_get_keywords_cursor_rejects_changed_params(mock_search_kms_pattern: MagicMock) -> None:
    """When cursor is present, changing query/scheme params must raise a ToolError."""
    tool = _load_tool()
    mock_search_kms_pattern.return_value = [_make_concept(0)]

    cursor = encode_cursor("kms", {"offset": 10, "query": "ORIGINAL", "scheme": "sciencekeywords"})

    with pytest.raises(ToolError) as exc_info:
        tool.get_keywords(query="CHANGED", scheme=None, limit=10, cursor=cursor)

    assert "query-scoped" in str(exc_info.value).lower()


def test_get_keywords_fields_filter(mock_search_kms_pattern: MagicMock) -> None:
    """fields parameter strips unrequested keys, keeping uuid as mandatory."""
    tool = _load_tool()
    mock_search_kms_pattern.return_value = [_make_concept(0)]

    result = tool.get_keywords(query="KEYWORD", fields=["prefLabel"])

    assert result["status"] == SearchStatus.SUCCESS
    item = result["keywords"][0]
    assert "uuid" in item
    assert "prefLabel" in item
    assert "scheme" not in item
    assert "definition" not in item


def test_get_keywords_validation_error():
    """Empty query should trigger an input validation ToolError."""
    from tools.get_keywords.tool import get_keywords

    with pytest.raises(ToolError):
        get_keywords(query="")  # min_length is 1, triggers validation error


def test_get_keywords_validation_error_too_big_limit():
    """Oversized limit should trigger an input validation ToolError."""
    from tools.get_keywords.tool import get_keywords

    with pytest.raises(ToolError):
        get_keywords(query="", limit=100)


def test_get_keywords_safe_exception_surfacing(monkeypatch):
    """Known exceptions should surface their message; unknown exceptions must not leak detail."""
    from tools.get_keywords.tool import get_keywords

    def fake_search_value_error(*args, **kwargs):
        raise ValueError("Safe validation error")

    monkeypatch.setattr("tools.get_keywords.tool.search_kms_pattern", fake_search_value_error)

    with pytest.raises(ToolError) as exc_info:
        get_keywords(query="modis")

    assert "Safe validation error" in str(exc_info.value)

    def fake_search_generic_error(*args, **kwargs):
        raise Exception("Fake secret")

    monkeypatch.setattr("tools.get_keywords.tool.search_kms_pattern", fake_search_generic_error)

    with pytest.raises(ToolError) as exc_info:
        get_keywords(query="modis")

    assert "Fake secret" not in str(exc_info.value)
    assert "unexpected error" in str(exc_info.value).lower()
