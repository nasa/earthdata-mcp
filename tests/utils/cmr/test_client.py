"""Tests for CMR API client."""

from unittest.mock import Mock

import pytest
import requests

from util.cmr.client import (
    CMRError,
    CMRSearchResponse,
    fetch_associations,
    fetch_concept,
    search_cmr,
)


def _make_response(*, json_data=None, headers=None):
    """Build a mock requests.Response with configurable attributes."""
    response = Mock()
    response.json.return_value = json_data or {}
    response.headers = {
        "CMR-Hits": "0",
        "CMR-Took": "5",
        **(headers or {}),
    }
    response.raise_for_status.return_value = None
    return response


class TestFetchConcept:
    """Test fetch_concept function."""

    def test_returns_concept_metadata(self, monkeypatch):
        """Should return parsed JSON for a valid concept."""
        expected = {"meta": {"concept-id": "C1234-PROVIDER"}, "umm": {}}
        mock_get = Mock(return_value=_make_response(json_data=expected))
        monkeypatch.setattr("util.cmr.client.requests.get", mock_get)

        result = fetch_concept("C1234-PROVIDER", "1")

        assert result == expected
        mock_get.assert_called_once()
        assert "C1234-PROVIDER/1.umm_json" in mock_get.call_args[0][0]

    def test_raises_cmr_error_on_request_failure(self, monkeypatch):
        """Should raise CMRError when the request fails."""
        monkeypatch.setattr(
            "util.cmr.client.requests.get",
            Mock(side_effect=requests.ConnectionError("timeout")),
        )

        with pytest.raises(CMRError, match="Failed to fetch C1234-PROVIDER"):
            fetch_concept("C1234-PROVIDER", "1")

    def test_raises_cmr_error_on_http_error(self, monkeypatch):
        """Should raise CMRError on non-2xx HTTP response."""
        bad_response = _make_response()
        bad_response.raise_for_status.side_effect = requests.HTTPError("404 Not Found")
        monkeypatch.setattr("util.cmr.client.requests.get", Mock(return_value=bad_response))

        with pytest.raises(CMRError):
            fetch_concept("C9999-MISSING", "1")


class TestFetchAssociations:
    """Test fetch_associations function."""

    def test_returns_associations_for_collection(self, monkeypatch):
        """Should return associations dict from collection metadata."""
        associations = {"variables": ["V1-PROVIDER"], "citations": []}
        json_data = {"items": [{"meta": {"associations": associations}, "umm": {}}]}
        monkeypatch.setattr(
            "util.cmr.client.requests.get",
            Mock(return_value=_make_response(json_data=json_data)),
        )

        result = fetch_associations("C1234-PROVIDER")

        assert result == associations

    def test_returns_empty_dict_when_no_items(self, monkeypatch):
        """Should return empty dict when collection not found."""
        monkeypatch.setattr(
            "util.cmr.client.requests.get",
            Mock(return_value=_make_response(json_data={"items": []})),
        )

        result = fetch_associations("C9999-MISSING")

        assert result == {}

    def test_returns_empty_dict_on_request_failure(self, monkeypatch):
        """Should return empty dict (not raise) when request fails."""
        monkeypatch.setattr(
            "util.cmr.client.requests.get",
            Mock(side_effect=requests.ConnectionError("timeout")),
        )

        result = fetch_associations("C1234-PROVIDER")

        assert result == {}

    def test_returns_empty_dict_when_no_associations_key(self, monkeypatch):
        """Should return empty dict when meta has no associations key."""
        json_data = {"items": [{"meta": {}, "umm": {}}]}
        monkeypatch.setattr(
            "util.cmr.client.requests.get",
            Mock(return_value=_make_response(json_data=json_data)),
        )

        result = fetch_associations("C1234-PROVIDER")

        assert result == {}


class TestSearchCmrGet:
    """Test search_cmr with GET method (default)."""

    def test_raises_on_unsupported_concept_type(self):
        """Should raise CMRError for unknown concept types."""
        with pytest.raises(CMRError, match="Unsupported concept_type"):
            list(search_cmr("unknown_type", {}))

    def test_yields_single_page_of_results(self, monkeypatch):
        """Should yield one CMRSearchResponse for a single page of results."""
        items = [{"meta": {"concept-id": "C1-P"}, "umm": {}}]
        response = _make_response(
            json_data={"items": items},
            headers={"CMR-Hits": "1", "CMR-Took": "10"},
        )
        monkeypatch.setattr("util.cmr.client.requests.get", Mock(return_value=response))

        pages = list(search_cmr("collection", {"keyword": "modis"}, page_size=10))

        assert len(pages) == 1
        assert isinstance(pages[0], CMRSearchResponse)
        assert pages[0].items == items
        assert pages[0].total_hits == 1
        assert pages[0].took_ms == 10
        assert pages[0].page_size == 1

    def test_paginates_using_search_after(self, monkeypatch):
        """Should follow search-after token until exhausted."""
        page1_items = [{"meta": {"concept-id": "C1-P"}, "umm": {}}]
        page2_items = [{"meta": {"concept-id": "C2-P"}, "umm": {}}]

        page1 = _make_response(
            json_data={"items": page1_items},
            headers={"CMR-Hits": "2", "CMR-Took": "5", "CMR-Search-After": "token-abc"},
        )
        page2 = _make_response(
            json_data={"items": page2_items},
            headers={"CMR-Hits": "2", "CMR-Took": "4"},
        )

        mock_get = Mock(side_effect=[page1, page2])
        monkeypatch.setattr("util.cmr.client.requests.get", mock_get)

        pages = list(search_cmr("collection", {}, page_size=1))

        assert len(pages) == 2
        assert pages[0].items == page1_items
        assert pages[1].items == page2_items
        # Second request should carry the search-after header
        second_call_headers = mock_get.call_args_list[1][1]["headers"]
        assert second_call_headers["CMR-Search-After"] == "token-abc"

    def test_stops_when_no_items_returned(self, monkeypatch):
        """Should stop pagination when an empty items list is returned."""
        response = _make_response(
            json_data={"items": []},
            headers={"CMR-Hits": "0", "CMR-Took": "2"},
        )
        monkeypatch.setattr("util.cmr.client.requests.get", Mock(return_value=response))

        pages = list(search_cmr("collection", {}))

        assert pages == []

    def test_raises_cmr_error_on_request_failure(self, monkeypatch):
        """Should raise CMRError when the HTTP request fails."""
        monkeypatch.setattr(
            "util.cmr.client.requests.get",
            Mock(side_effect=requests.ConnectionError("refused")),
        )

        with pytest.raises(CMRError, match="CMR request failed"):
            list(search_cmr("collection", {}))

    def test_count_only_query_returns_single_page(self, monkeypatch):
        """Should yield one page with empty items for page_size=0 count queries."""
        response = _make_response(
            json_data={"items": []},
            headers={"CMR-Hits": "42", "CMR-Took": "3"},
        )
        monkeypatch.setattr("util.cmr.client.requests.get", Mock(return_value=response))

        pages = list(search_cmr("granule", {"collection_concept_id": "C1-P"}, page_size=0))

        assert len(pages) == 1
        assert pages[0].total_hits == 42
        assert pages[0].items == []
        assert pages[0].page_size == 0


class TestSearchCmrPost:
    """Test search_cmr with POST method."""

    def test_uses_post_when_method_is_post(self, monkeypatch):
        """Should call requests.post instead of requests.get."""
        items = [{"meta": {"concept-id": "C1-P"}, "umm": {}}]
        response = _make_response(
            json_data={"items": items},
            headers={"CMR-Hits": "1", "CMR-Took": "8"},
        )
        mock_post = Mock(return_value=response)
        mock_get = Mock()
        monkeypatch.setattr("util.cmr.client.requests.post", mock_post)
        monkeypatch.setattr("util.cmr.client.requests.get", mock_get)

        pages = list(search_cmr("granule", {"collection_concept_id": "C1-P"}, method="POST"))

        mock_post.assert_called_once()
        mock_get.assert_not_called()
        assert len(pages) == 1
        assert pages[0].items == items

    def test_passes_files_in_post_request(self, monkeypatch):
        """Should forward the files dict to requests.post for spatial queries."""
        response = _make_response(
            json_data={"items": []},
            headers={"CMR-Hits": "0", "CMR-Took": "5"},
        )
        mock_post = Mock(return_value=response)
        monkeypatch.setattr("util.cmr.client.requests.post", mock_post)

        shapefile = {"shapefile": ("shapefile", b"geojson-bytes", "application/geo+json")}
        list(search_cmr("granule", {"page_size": 0}, method="POST", files=shapefile))

        call_kwargs = mock_post.call_args[1]
        assert call_kwargs["files"] == shapefile

    def test_passes_params_as_data_in_post_request(self, monkeypatch):
        """Should send search params as form data (not query string) in POST."""
        response = _make_response(
            json_data={"items": []},
            headers={"CMR-Hits": "0", "CMR-Took": "3"},
        )
        mock_post = Mock(return_value=response)
        monkeypatch.setattr("util.cmr.client.requests.post", mock_post)

        params = {"collection_concept_id": "C1-P", "page_size": 0}
        list(search_cmr("granule", params, page_size=0, method="POST"))

        call_kwargs = mock_post.call_args[1]
        assert "data" in call_kwargs
        assert call_kwargs["data"]["collection_concept_id"] == "C1-P"

    def test_count_only_post_returns_total_hits(self, monkeypatch):
        """POST count-only query (page_size=0) should return correct hit count."""
        response = _make_response(
            json_data={"items": []},
            headers={"CMR-Hits": "137", "CMR-Took": "6"},
        )
        monkeypatch.setattr("util.cmr.client.requests.post", Mock(return_value=response))

        pages = list(
            search_cmr(
                "granule",
                {"collection_concept_id": "C1-P"},
                page_size=0,
                method="POST",
            )
        )

        assert len(pages) == 1
        assert pages[0].total_hits == 137
        assert pages[0].items == []

    def test_raises_cmr_error_on_post_failure(self, monkeypatch):
        """Should raise CMRError when the POST request fails."""
        monkeypatch.setattr(
            "util.cmr.client.requests.post",
            Mock(side_effect=requests.ConnectionError("refused")),
        )

        with pytest.raises(CMRError, match="CMR request failed"):
            list(search_cmr("granule", {}, method="POST"))

    def test_method_matching_is_case_insensitive(self, monkeypatch):
        """Should treat 'post' (lowercase) the same as 'POST'."""
        items = [{"meta": {"concept-id": "C1-P"}, "umm": {}}]
        response = _make_response(
            json_data={"items": items},
            headers={"CMR-Hits": "1", "CMR-Took": "4"},
        )
        mock_post = Mock(return_value=response)
        mock_get = Mock()
        monkeypatch.setattr("util.cmr.client.requests.post", mock_post)
        monkeypatch.setattr("util.cmr.client.requests.get", mock_get)

        list(search_cmr("granule", {}, method="post"))  # type: ignore[arg-type]

        mock_post.assert_called_once()
        mock_get.assert_not_called()


class TestClientIdHeader:
    """Tests that the Client-Id header is sent on every request type."""

    def test_fetch_concept_sends_client_id(self, monkeypatch):
        """fetch_concept should include Client-Id in the request headers."""
        mock_get = Mock(return_value=_make_response(json_data={}))
        monkeypatch.setattr("util.cmr.client.requests.get", mock_get)
        monkeypatch.setattr("util.cmr.client.CLIENT_ID", "eed-test-mcp")

        fetch_concept("C1234-PROVIDER", "1")

        sent_headers = mock_get.call_args[1]["headers"]
        assert sent_headers["Client-Id"] == "eed-test-mcp"

    def test_fetch_associations_sends_client_id(self, monkeypatch):
        """fetch_associations should include Client-Id in the request headers."""
        json_data = {"items": [{"meta": {"associations": {}}, "umm": {}}]}
        mock_get = Mock(return_value=_make_response(json_data=json_data))
        monkeypatch.setattr("util.cmr.client.requests.get", mock_get)
        monkeypatch.setattr("util.cmr.client.CLIENT_ID", "eed-test-mcp")

        fetch_associations("C1234-PROVIDER")

        sent_headers = mock_get.call_args[1]["headers"]
        assert sent_headers["Client-Id"] == "eed-test-mcp"

    def test_search_cmr_get_sends_client_id(self, monkeypatch):
        """search_cmr GET should include Client-Id in the request headers."""
        items = [{"meta": {"concept-id": "C1-P"}, "umm": {}}]
        mock_get = Mock(return_value=_make_response(json_data={"items": items}))
        monkeypatch.setattr("util.cmr.client.requests.get", mock_get)
        monkeypatch.setattr("util.cmr.client.CLIENT_ID", "eed-test-mcp")

        list(search_cmr("collection", {}, page_size=1))

        sent_headers = mock_get.call_args[1]["headers"]
        assert sent_headers["Client-Id"] == "eed-test-mcp"

    def test_search_cmr_post_sends_client_id(self, monkeypatch):
        """search_cmr POST should include Client-Id in the request headers."""
        items = [{"meta": {"concept-id": "C1-P"}, "umm": {}}]
        mock_post = Mock(return_value=_make_response(json_data={"items": items}))
        monkeypatch.setattr("util.cmr.client.requests.post", mock_post)
        monkeypatch.setattr("util.cmr.client.CLIENT_ID", "eed-test-mcp")

        list(search_cmr("granule", {}, page_size=1, method="POST"))

        sent_headers = mock_post.call_args[1]["headers"]
        assert sent_headers["Client-Id"] == "eed-test-mcp"
