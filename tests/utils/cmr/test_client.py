"""Tests for CMR API client."""

from unittest.mock import Mock

import pytest
import requests

from util.cmr.client import (
    CMRError,
    CMRSearchResponse,
    _extract_tool_info,
    fetch_associations,
    fetch_collection_tags,
    fetch_concept,
    fetch_tool_metadata,
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


class TestFetchCollectionTags:
    """Tests for fetch_collection_tags function."""

    def test_returns_tags_for_collection(self, monkeypatch):
        """Should return the tags dict from the first feed entry."""
        tags = {
            "edsc.extra.serverless.gibs": {"data": [{"product": "MODIS_Terra", "geographic": True}]}
        }
        json_data = {"feed": {"entry": [{"id": "C1234-PROVIDER", "tags": tags}]}}
        monkeypatch.setattr(
            "util.cmr.client.requests.get",
            Mock(return_value=_make_response(json_data=json_data)),
        )

        result = fetch_collection_tags("C1234-PROVIDER")

        assert result == tags

    def test_returns_empty_dict_when_no_entries(self, monkeypatch):
        """Should return empty dict when feed has no entries."""
        monkeypatch.setattr(
            "util.cmr.client.requests.get",
            Mock(return_value=_make_response(json_data={"feed": {"entry": []}})),
        )

        result = fetch_collection_tags("C9999-MISSING")

        assert result == {}

    def test_returns_empty_dict_when_no_tags_key(self, monkeypatch):
        """Should return empty dict when entry has no tags field."""
        json_data = {"feed": {"entry": [{"id": "C1234-PROVIDER"}]}}
        monkeypatch.setattr(
            "util.cmr.client.requests.get",
            Mock(return_value=_make_response(json_data=json_data)),
        )

        result = fetch_collection_tags("C1234-PROVIDER")

        assert result == {}

    def test_returns_empty_dict_on_request_failure(self, monkeypatch):
        """Should return empty dict (not raise) when request fails."""
        monkeypatch.setattr(
            "util.cmr.client.requests.get",
            Mock(side_effect=requests.ConnectionError("timeout")),
        )

        result = fetch_collection_tags("C1234-PROVIDER")

        assert result == {}

    def test_sends_include_tags_param(self, monkeypatch):
        """Should include include_tags=edsc.* in the request params."""
        json_data = {"feed": {"entry": []}}
        mock_get = Mock(return_value=_make_response(json_data=json_data))
        monkeypatch.setattr("util.cmr.client.requests.get", mock_get)

        fetch_collection_tags("C1234-PROVIDER")

        params = mock_get.call_args[1]["params"]
        assert params["include_tags"] == "edsc.*"
        assert params["concept_id"] == "C1234-PROVIDER"

    def test_uses_collections_json_endpoint(self, monkeypatch):
        """Should call the /search/collections.json endpoint."""
        json_data = {"feed": {"entry": []}}
        mock_get = Mock(return_value=_make_response(json_data=json_data))
        monkeypatch.setattr("util.cmr.client.requests.get", mock_get)

        fetch_collection_tags("C1234-PROVIDER")

        assert "collections.json" in mock_get.call_args[0][0]

    def test_sends_client_id_header(self, monkeypatch):
        """Should include Client-Id in request headers."""
        json_data = {"feed": {"entry": []}}
        mock_get = Mock(return_value=_make_response(json_data=json_data))
        monkeypatch.setattr("util.cmr.client.requests.get", mock_get)
        monkeypatch.setattr("util.cmr.client.CLIENT_ID", "eed-test-mcp")

        fetch_collection_tags("C1234-PROVIDER")

        assert mock_get.call_args[1]["headers"]["Client-Id"] == "eed-test-mcp"


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

    def test_uses_provided_search_after_for_first_request(self, monkeypatch):
        """Should include an incoming search-after token on the first request."""
        items = [{"meta": {"concept-id": "C1-P"}, "umm": {}}]
        response = _make_response(
            json_data={"items": items},
            headers={"CMR-Hits": "1", "CMR-Took": "5"},
        )
        mock_get = Mock(return_value=response)
        monkeypatch.setattr("util.cmr.client.requests.get", mock_get)

        pages = list(search_cmr("collection", {}, page_size=10, search_after='["token"]'))

        assert len(pages) == 1
        sent_headers = mock_get.call_args[1]["headers"]
        assert sent_headers["CMR-Search-After"] == '["token"]'

    def test_stops_when_no_items_returned(self, monkeypatch):
        """Should stop pagination when an empty items list is returned."""
        response = _make_response(
            json_data={"items": []},
            headers={"CMR-Hits": "0", "CMR-Took": "2"},
        )
        monkeypatch.setattr("util.cmr.client.requests.get", Mock(return_value=response))

        pages = list(search_cmr("collection", {}))

        assert not pages

    def test_raises_cmr_error_on_request_failure(self, monkeypatch):
        """Should raise CMRError when the HTTP request fails."""
        monkeypatch.setattr(
            "util.cmr.client.requests.get",
            Mock(side_effect=requests.ConnectionError("refused")),
        )

        with pytest.raises(CMRError, match="CMR request failed"):
            list(search_cmr("collection", {}))

    def test_includes_cmr_error_details_from_http_response(self, monkeypatch):
        """Should surface CMR error payload details when a request returns HTTP 400."""
        bad_response = _make_response(json_data={"errors": ["Invalid shapefile geometry"]})
        bad_response.raise_for_status.side_effect = requests.HTTPError(
            "400 Client Error", response=bad_response
        )
        monkeypatch.setattr("util.cmr.client.requests.get", Mock(return_value=bad_response))

        with pytest.raises(CMRError, match="Invalid shapefile geometry"):
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


class TestExtractToolInfo:
    """Test _extract_tool_info helper."""

    def test_extracts_name_url_template_and_query_inputs(self):
        """Should extract name, url_template, and typed query_inputs from PotentialAction."""
        item = {
            "meta": {"concept-id": "TL1234-PROV"},
            "umm": {
                "Name": "Giovanni",
                "Type": "Web User Interface",
                "PotentialAction": {
                    "Type": "SearchAction",
                    "Target": {
                        "Type": "EntryPoint",
                        "UrlTemplate": "https://giovanni.gsfc.nasa.gov/giovanni/#service=TmAvMp{?dataKeyword,starttime,endtime,bbox}",
                        "HttpMethod": ["GET"],
                    },
                    "QueryInput": [
                        {
                            "ValueName": "dataKeyword",
                            "ValueRequired": False,
                            "ValueType": "shortName",
                        },
                        {
                            "ValueName": "starttime",
                            "ValueRequired": True,
                            "ValueType": "https://schema.org/startDate",
                        },
                        {
                            "ValueName": "endtime",
                            "ValueRequired": False,
                            "ValueType": "https://schema.org/endDate",
                        },
                        {
                            "ValueName": "bbox",
                            "ValueRequired": False,
                            "ValueType": "https://schema.org/box",
                        },
                    ],
                },
            },
        }

        result = _extract_tool_info(item)

        assert result == {
            "name": "Giovanni",
            "base_url": None,
            "url_template": "https://giovanni.gsfc.nasa.gov/giovanni/#service=TmAvMp{?dataKeyword,starttime,endtime,bbox}",
            "query_inputs": [
                {"value_name": "dataKeyword", "value_type": "shortName", "required": False},
                {
                    "value_name": "starttime",
                    "value_type": "https://schema.org/startDate",
                    "required": True,
                },
                {
                    "value_name": "endtime",
                    "value_type": "https://schema.org/endDate",
                    "required": False,
                },
                {"value_name": "bbox", "value_type": "https://schema.org/box", "required": False},
            ],
            "topic": None,
        }

    def test_returns_none_for_missing_umm_key(self):
        """Should return None (filtered) when the umm key is absent — type unknown."""
        item = {"meta": {"concept-id": "TL1234-PROV"}}

        assert _extract_tool_info(item) is None

    def test_returns_none_url_template_when_potential_action_absent(self):
        """Should return None for url_template when PotentialAction is not in umm."""
        item = {
            "meta": {"concept-id": "TL1234-PROV"},
            "umm": {"Name": "My Tool", "Type": "Web User Interface"},
        }

        result = _extract_tool_info(item)

        assert result["name"] == "My Tool"
        assert result["url_template"] is None
        assert result["query_inputs"] == []

    def test_returns_empty_query_inputs_when_query_input_key_absent(self):
        """Should return empty query_inputs when QueryInput is missing from PotentialAction."""
        item = {
            "umm": {
                "Name": "My Tool",
                "Type": "Web User Interface",
                "PotentialAction": {
                    "Target": {"UrlTemplate": "https://example.com{?q}"},
                },
            }
        }

        result = _extract_tool_info(item)

        assert result["url_template"] == "https://example.com{?q}"
        assert result["query_inputs"] == []

    def test_returns_none_for_completely_empty_item(self):
        """Should return None (filtered) for a completely empty item — type unknown."""
        assert _extract_tool_info({}) is None

    def test_extracts_base_url_from_url_entry(self):
        """Should extract URL.URLValue as base_url."""
        item = {
            "umm": {
                "Name": "Giovanni",
                "Type": "Web User Interface",
                "URL": {
                    "URLContentType": "DistributionURL",
                    "Type": "GET SERVICE",
                    "URLValue": "https://giovanni.gsfc.nasa.gov",
                },
            }
        }
        result = _extract_tool_info(item)
        assert result["base_url"] == "https://giovanni.gsfc.nasa.gov"

    def test_returns_none_base_url_when_url_entry_absent(self):
        """Should return None base_url when URL is not present in umm."""
        item = {"umm": {"Name": "Tool", "Type": "Web User Interface"}}
        result = _extract_tool_info(item)
        assert result["base_url"] is None

    def test_extracts_topic_from_tool_keywords(self):
        """Should extract ToolTopic from the first ToolKeywords entry."""
        item = {
            "umm": {
                "Name": "Giovanni",
                "Type": "Web User Interface",
                "ToolKeywords": [
                    {
                        "ToolCategory": "EARTH SCIENCE SERVICES",
                        "ToolTopic": "DATA ANALYSIS AND VISUALIZATION",
                    }
                ],
            }
        }
        result = _extract_tool_info(item)
        assert result["topic"] == "Data analysis and visualization"

    def test_returns_none_topic_when_tool_keywords_absent(self):
        """Should return None topic when ToolKeywords is not present."""
        item = {"umm": {"Name": "Tool", "Type": "Web User Interface"}}
        result = _extract_tool_info(item)
        assert result["topic"] is None

    def test_defaults_required_to_false_when_value_required_absent(self):
        """Should default required=False when ValueRequired is missing from a QueryInput."""
        item = {
            "umm": {
                "Name": "Tool",
                "Type": "Web User Interface",
                "PotentialAction": {
                    "Target": {"UrlTemplate": "https://example.com{?q}"},
                    "QueryInput": [{"ValueName": "q", "ValueType": "shortName"}],
                },
            }
        }

        result = _extract_tool_info(item)

        assert result["query_inputs"][0]["required"] is False

    def test_returns_none_for_non_eligible_tool_type(self):
        """Should return None when Type is not 'Web User Interface' or 'Web Portal'."""
        item = {"umm": {"Name": "My Algo", "Type": "Algorithm"}}
        assert _extract_tool_info(item) is None

    def test_accepts_web_portal_type(self):
        """Should return a dict when Type is 'Web Portal'."""
        item = {"umm": {"Name": "Earthdata Search", "Type": "Web Portal"}}
        result = _extract_tool_info(item)
        assert result is not None
        assert result["name"] == "Earthdata Search"

    def test_returns_none_when_potential_action_type_is_not_search_action(self):
        """Should return None when PotentialAction.Type is something other than SearchAction."""
        item = {
            "umm": {
                "Name": "Tool",
                "Type": "Web User Interface",
                "PotentialAction": {
                    "Type": "ViewAction",
                    "Target": {"UrlTemplate": "https://example.com{?q}"},
                },
            }
        }
        assert _extract_tool_info(item) is None

    def test_accepts_potential_action_without_type_field(self):
        """Should accept tools whose PotentialAction has no Type field."""
        item = {
            "umm": {
                "Name": "Tool",
                "Type": "Web User Interface",
                "PotentialAction": {
                    "Target": {"UrlTemplate": "https://example.com{?q}"},
                },
            }
        }
        result = _extract_tool_info(item)
        assert result is not None
        assert result["url_template"] == "https://example.com{?q}"


class TestFetchToolMetadata:
    """Test fetch_tool_metadata function."""

    def test_returns_empty_list_when_no_ids_given(self):
        """Should skip the HTTP call and return [] immediately for empty input."""
        result = fetch_tool_metadata([])

        assert result == []

    def test_returns_extracted_metadata_for_valid_response(self, monkeypatch):
        """Should return list of extracted tool dicts for a successful response."""
        items = [
            {
                "meta": {"concept-id": "TL1-PROV"},
                "umm": {
                    "Name": "Tool A",
                    "Type": "Web User Interface",
                    "PotentialAction": {
                        "Type": "SearchAction",
                        "Target": {"UrlTemplate": "https://tool-a.example.com{?q}"},
                        "QueryInput": [
                            {"ValueName": "q", "ValueRequired": False, "ValueType": "shortName"}
                        ],
                    },
                },
            },
            {
                "meta": {"concept-id": "TL2-PROV"},
                "umm": {
                    "Name": "Tool B",
                    "Type": "Web Portal",
                    "PotentialAction": {
                        "Target": {"UrlTemplate": "https://tool-b.example.com{?q}"},
                        "QueryInput": [],
                    },
                },
            },
        ]
        mock_get = Mock(
            return_value=_make_response(
                json_data={"items": items},
                headers={"CMR-Hits": "2", "CMR-Took": "5"},
            )
        )
        monkeypatch.setattr("util.cmr.client.requests.get", mock_get)

        result = fetch_tool_metadata(["TL1-PROV", "TL2-PROV"])

        assert len(result) == 2
        assert result[0]["name"] == "Tool A"
        assert result[0]["url_template"] == "https://tool-a.example.com{?q}"
        assert result[1]["name"] == "Tool B"
        assert result[1]["query_inputs"] == []

    def test_batches_all_ids_in_single_request(self, monkeypatch):
        """Should send all concept IDs in one request, not one per ID."""
        mock_get = Mock(return_value=_make_response(json_data={"items": []}))
        monkeypatch.setattr("util.cmr.client.requests.get", mock_get)

        fetch_tool_metadata(["TL1-PROV", "TL2-PROV", "TL3-PROV"])

        mock_get.assert_called_once()

    def test_passes_page_size_equal_to_number_of_ids(self, monkeypatch):
        """page_size should equal the number of requested IDs to fetch all in one page."""
        mock_get = Mock(return_value=_make_response(json_data={"items": []}))
        monkeypatch.setattr("util.cmr.client.requests.get", mock_get)

        fetch_tool_metadata(["TL1-PROV", "TL2-PROV", "TL3-PROV"])

        call_params = mock_get.call_args[1]["params"]
        assert call_params["page_size"] == 3

    def test_filters_out_ineligible_tool_types(self, monkeypatch):
        """Items whose Type is not Web UI/Portal should be silently excluded."""
        items = [
            {
                "meta": {"concept-id": "TL1-PROV"},
                "umm": {"Name": "Web Tool", "Type": "Web User Interface"},
            },
            {"meta": {"concept-id": "TL2-PROV"}, "umm": {"Name": "Algorithm", "Type": "Algorithm"}},
        ]
        monkeypatch.setattr(
            "util.cmr.client.requests.get",
            Mock(return_value=_make_response(json_data={"items": items})),
        )

        result = fetch_tool_metadata(["TL1-PROV", "TL2-PROV"])

        assert len(result) == 1
        assert result[0]["name"] == "Web Tool"

    def test_returns_empty_list_on_request_failure(self, monkeypatch):
        """Should return [] (not raise) when the HTTP request fails."""
        monkeypatch.setattr(
            "util.cmr.client.requests.get",
            Mock(side_effect=requests.ConnectionError("timeout")),
        )

        result = fetch_tool_metadata(["TL1-PROV"])

        assert result == []

    def test_returns_empty_list_when_response_has_no_items(self, monkeypatch):
        """Should return [] when CMR returns an empty items list."""
        monkeypatch.setattr(
            "util.cmr.client.requests.get",
            Mock(return_value=_make_response(json_data={"items": []})),
        )

        result = fetch_tool_metadata(["TL1-PROV"])

        assert result == []

    def test_sends_client_id_header(self, monkeypatch):
        """Should include Client-Id header in the tool metadata request."""
        mock_get = Mock(return_value=_make_response(json_data={"items": []}))
        monkeypatch.setattr("util.cmr.client.requests.get", mock_get)
        monkeypatch.setattr("util.cmr.client.CLIENT_ID", "eed-test-mcp")

        fetch_tool_metadata(["TL1-PROV"])

        sent_headers = mock_get.call_args[1]["headers"]
        assert sent_headers["Client-Id"] == "eed-test-mcp"


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


class TestSearchCmrService:
    """Test search_cmr for the 'service' concept type."""

    def test_service_concept_type_is_supported(self, monkeypatch):
        """search_cmr('service', ...) should not raise CMRError for an unsupported type."""
        items = [{"meta": {"concept-id": "S1-P"}, "umm": {}}]
        monkeypatch.setattr(
            "util.cmr.client.requests.get",
            Mock(
                return_value=_make_response(
                    json_data={"items": items},
                    headers={"CMR-Hits": "1", "CMR-Took": "5"},
                )
            ),
        )

        pages = list(search_cmr("service", {"concept_id[]": ["S1-PROVIDER"]}))

        assert len(pages) == 1
        assert pages[0].items == items

    def test_uses_services_umm_json_url(self, monkeypatch):
        """Should call the /search/services.umm_json endpoint."""
        mock_get = Mock(
            return_value=_make_response(
                json_data={"items": []},
                headers={"CMR-Hits": "0", "CMR-Took": "3"},
            )
        )
        monkeypatch.setattr("util.cmr.client.requests.get", mock_get)

        list(search_cmr("service", {"concept_id[]": ["S1-PROVIDER"]}))

        called_url = mock_get.call_args[0][0]
        assert "services.umm_json" in called_url

    def test_returns_cmrsearchresponse_with_service_items(self, monkeypatch):
        """Should return a CMRSearchResponse with the service items and metadata."""
        service_item = {
            "meta": {"concept-id": "S1-PROVIDER"},
            "umm": {"Name": "My OPeNDAP Service", "Type": "OPeNDAP"},
        }
        monkeypatch.setattr(
            "util.cmr.client.requests.get",
            Mock(
                return_value=_make_response(
                    json_data={"items": [service_item]},
                    headers={"CMR-Hits": "1", "CMR-Took": "7"},
                )
            ),
        )

        pages = list(search_cmr("service", {"concept_id[]": ["S1-PROVIDER"]}))

        assert isinstance(pages[0], CMRSearchResponse)
        assert pages[0].total_hits == 1
        assert pages[0].took_ms == 7
        assert pages[0].items[0]["umm"]["Type"] == "OPeNDAP"
