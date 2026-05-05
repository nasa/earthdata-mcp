"""Tests for the get_keywords MCP tool."""

import importlib
import types
from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
import requests

from models.tools.cmr_search import SearchStatus


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

    result = tool.get_keywords(query="ERROR_TERM")

    assert result["status"] == SearchStatus.ERROR
    assert result["total_hits"] == 0
    assert len(result["keywords"]) == 0
    assert "Failed to communicate with KMS API" in result["error_message"]


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

    result = tool.get_keywords(query="TEST")

    assert result["status"] == SearchStatus.ERROR
    assert "unexpected error" in result["error_message"].lower()


def test_get_keywords_calls_trace_update(mock_search_kms_pattern):
    """Test telemetry tracing."""
    tool = _load_tool()
    mock_search_kms_pattern.return_value = []

    with patch.object(tool, "trace_update") as mock_trace_update:
        tool.get_keywords(query="TEST")

    assert mock_trace_update.called
