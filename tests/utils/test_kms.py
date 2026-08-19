"""Tests for the KMS client utility."""

from unittest.mock import Mock, patch

import pytest
import requests

from util.kms.client import search_kms_pattern


@pytest.fixture
def mock_requests_get():
    """Mock requests.get."""
    with patch("requests.get") as mock_get:
        yield mock_get


def test_search_kms_pattern_global(mock_requests_get):
    """Test global search URL construction and parsing."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "hits": 1,
        "concepts": [{"uuid": "123", "prefLabel": "TEST"}],
    }
    mock_requests_get.return_value = mock_response

    results = search_kms_pattern("TEST QUERY")

    assert len(results) == 1
    assert results[0]["prefLabel"] == "TEST"

    mock_requests_get.assert_called_once()
    args, kwargs = mock_requests_get.call_args
    assert args[0] == "https://cmr.earthdata.nasa.gov/kms/concepts/pattern/TEST%20QUERY"
    assert kwargs["params"]["format"] == "json"
    assert kwargs["timeout"] == 10


def test_search_kms_pattern_scheme(mock_requests_get):
    """Test scheme-specific search URL construction and parsing."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "hits": 1,
        "concepts": [{"uuid": "123", "prefLabel": "TEST"}],
    }
    mock_requests_get.return_value = mock_response

    results = search_kms_pattern("TEST", scheme="instruments")

    assert len(results) == 1
    mock_requests_get.assert_called_once()
    args, kwargs = mock_requests_get.call_args
    assert (
        args[0]
        == "https://cmr.earthdata.nasa.gov/kms/concepts/concept_scheme/instruments/pattern/TEST"
    )
    assert kwargs["params"]["format"] == "json"
    assert kwargs["timeout"] == 10


def test_search_kms_pattern_no_results(mock_requests_get):
    """Test behavior when API returns 0 hits."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"hits": 0, "concepts": []}
    mock_requests_get.return_value = mock_response

    results = search_kms_pattern("FAKE")

    assert results == []


def test_search_kms_pattern_error(mock_requests_get):
    """Test behavior when API request fails."""
    mock_requests_get.side_effect = requests.RequestException("Timeout")

    with pytest.raises(requests.RequestException):
        search_kms_pattern("ERROR")
