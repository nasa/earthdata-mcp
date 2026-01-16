"""Tests for KMS (Keyword Management System) client."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from util.kms import clear_cache, lookup_term
from util.models import KMSTerm


@pytest.fixture(autouse=True)
def clear_kms_cache():
    """Clear the KMS cache before and after each test."""
    clear_cache()
    yield
    clear_cache()


class TestKMSTerm:
    """Tests for KMSTerm dataclass."""

    def test_creates_term_with_all_fields(self):
        """Should create term with all required fields."""
        term = KMSTerm(
            uuid="abc-123",
            scheme="sciencekeywords",
            term="PRECIPITATION",
            definition="Water falling from clouds",
        )
        assert term.uuid == "abc-123"
        assert term.scheme == "sciencekeywords"
        assert term.term == "PRECIPITATION"
        assert term.definition == "Water falling from clouds"

    def test_allows_none_definition(self):
        """Should allow None definition."""
        term = KMSTerm(
            uuid="abc-123",
            scheme="platforms",
            term="TERRA",
            definition=None,
        )
        assert term.definition is None


class TestLookupTerm:
    """Tests for lookup_term function."""

    def test_returns_term_on_successful_lookup(self):
        """Should return KMSTerm when term is found."""
        search_response = {"concepts": [{"prefLabel": "MODIS", "uuid": "modis-uuid-123"}]}
        concept_response = {"definition": "Moderate Resolution Imaging Spectroradiometer"}

        with patch("util.kms.client.requests.get") as mock_get:
            search_mock = MagicMock(status_code=200)
            search_mock.json.return_value = search_response
            search_mock.raise_for_status = MagicMock()

            concept_mock = MagicMock(status_code=200)
            concept_mock.json.return_value = concept_response
            concept_mock.raise_for_status = MagicMock()

            mock_get.side_effect = [search_mock, concept_mock]

            result = lookup_term("MODIS", "instruments")

            assert result is not None
            assert result.uuid == "modis-uuid-123"
            assert result.scheme == "instruments"
            assert result.term == "MODIS"
            assert result.definition == "Moderate Resolution Imaging Spectroradiometer"

    def test_returns_none_when_no_concepts_found(self):
        """Should return None when term is not found in KMS."""
        search_response = {"concepts": []}

        with patch("util.kms.client.requests.get") as mock_get:
            search_mock = MagicMock(status_code=200)
            search_mock.json.return_value = search_response
            search_mock.raise_for_status = MagicMock()
            mock_get.return_value = search_mock

            result = lookup_term("NONEXISTENT_TERM", "sciencekeywords")

            assert result is None

    def test_returns_none_on_network_error(self):
        """Should return None when network request fails."""
        with patch("util.kms.client.requests.get") as mock_get:
            mock_get.side_effect = requests.RequestException("Connection refused")

            result = lookup_term("MODIS", "instruments")

            assert result is None

    def test_returns_none_on_invalid_json(self):
        """Should return None when response is not valid JSON."""
        with patch("util.kms.client.requests.get") as mock_get:
            mock_response = MagicMock(status_code=200)
            mock_response.raise_for_status = MagicMock()
            mock_response.json.side_effect = ValueError("Invalid JSON")
            mock_get.return_value = mock_response

            result = lookup_term("MODIS", "instruments")

            assert result is None

    def test_prefers_exact_match(self):
        """Should prefer exact case-insensitive match over partial matches."""
        search_response = {
            "concepts": [
                {"prefLabel": "MODIS/TERRA", "uuid": "wrong-uuid"},
                {"prefLabel": "MODIS", "uuid": "correct-uuid"},
                {"prefLabel": "MODIS/AQUA", "uuid": "also-wrong"},
            ]
        }
        concept_response = {"definition": "The correct definition"}

        with patch("util.kms.client.requests.get") as mock_get:
            search_mock = MagicMock(status_code=200)
            search_mock.json.return_value = search_response
            search_mock.raise_for_status = MagicMock()

            concept_mock = MagicMock(status_code=200)
            concept_mock.json.return_value = concept_response
            concept_mock.raise_for_status = MagicMock()

            mock_get.side_effect = [search_mock, concept_mock]

            result = lookup_term("MODIS", "instruments")

            assert result.uuid == "correct-uuid"

    def test_falls_back_to_first_result_if_no_exact_match(self):
        """Should use first result if no exact match found."""
        search_response = {
            "concepts": [
                {"prefLabel": "MODIS/TERRA", "uuid": "first-uuid"},
                {"prefLabel": "MODIS/AQUA", "uuid": "second-uuid"},
            ]
        }
        concept_response = {"definition": "Some definition"}

        with patch("util.kms.client.requests.get") as mock_get:
            search_mock = MagicMock(status_code=200)
            search_mock.json.return_value = search_response
            search_mock.raise_for_status = MagicMock()

            concept_mock = MagicMock(status_code=200)
            concept_mock.json.return_value = concept_response
            concept_mock.raise_for_status = MagicMock()

            mock_get.side_effect = [search_mock, concept_mock]

            result = lookup_term("MODIS", "instruments")

            assert result.uuid == "first-uuid"

    def test_caches_results(self):
        """Should cache results to avoid duplicate API calls."""
        search_response = {"concepts": [{"prefLabel": "MODIS", "uuid": "modis-uuid"}]}
        concept_response = {"definition": "Cached definition"}

        with patch("util.kms.client.requests.get") as mock_get:
            search_mock = MagicMock(status_code=200)
            search_mock.json.return_value = search_response
            search_mock.raise_for_status = MagicMock()

            concept_mock = MagicMock(status_code=200)
            concept_mock.json.return_value = concept_response
            concept_mock.raise_for_status = MagicMock()

            mock_get.side_effect = [search_mock, concept_mock]

            # First call
            result1 = lookup_term("MODIS", "instruments")
            assert result1.definition == "Cached definition"
            assert mock_get.call_count == 2  # search + concept

            # Second call should use cache
            result2 = lookup_term("MODIS", "instruments")
            assert result2.definition == "Cached definition"
            assert mock_get.call_count == 2  # No additional calls

    def test_uses_correct_url_pattern(self):
        """Should construct correct KMS API URL."""
        search_response = {"concepts": []}

        with patch("util.kms.client.requests.get") as mock_get:
            search_mock = MagicMock(status_code=200)
            search_mock.json.return_value = search_response
            search_mock.raise_for_status = MagicMock()
            mock_get.return_value = search_mock

            lookup_term("TERRA", "platforms")

            call_args = mock_get.call_args
            url = call_args[0][0]
            assert "concept_scheme/platforms/pattern/TERRA" in url


class TestClearCache:
    """Tests for clear_cache function."""

    def test_clears_cached_results(self):
        """Should clear cached results so next lookup hits API."""
        search_response = {"concepts": [{"prefLabel": "MODIS", "uuid": "modis-uuid"}]}
        concept_response = {"definition": "First definition"}

        with patch("util.kms.client.requests.get") as mock_get:
            search_mock = MagicMock(status_code=200)
            search_mock.json.return_value = search_response
            search_mock.raise_for_status = MagicMock()

            concept_mock = MagicMock(status_code=200)
            concept_mock.json.return_value = concept_response
            concept_mock.raise_for_status = MagicMock()

            # Keep returning fresh mocks
            mock_get.side_effect = [
                search_mock,
                concept_mock,
                search_mock,
                concept_mock,
            ]

            # First call
            lookup_term("MODIS", "instruments")
            assert mock_get.call_count == 2

            # Clear cache
            clear_cache()

            # Second call should hit API again
            lookup_term("MODIS", "instruments")
            assert mock_get.call_count == 4  # 2 more calls
