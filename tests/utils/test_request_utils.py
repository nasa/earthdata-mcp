"""Tests for request_utils module"""

import base64
import json

import pytest

from util.request_utils import (
    parse_bool,
    parse_get_params,
    parse_post_body,
    parse_format,
    parse_request_parameters,
    create_empty_response,
    parse_nested_brackets,
    _parse_nested_key,
)


class TestParseBool:
    """Tests for parse_bool function"""

    def test_parse_bool_false_lowercase(self):
        """Test parsing 'false' string"""
        assert parse_bool("false") is False

    def test_parse_bool_false_uppercase(self):
        """Test parsing 'FALSE' string"""
        assert parse_bool("FALSE") is False

    def test_parse_bool_false_mixedcase(self):
        """Test parsing 'FaLsE' string"""
        assert parse_bool("FaLsE") is False

    def test_parse_bool_true_string(self):
        """Test parsing 'true' string"""
        assert parse_bool("true") is True

    def test_parse_bool_empty_string(self):
        """Test parsing empty string"""
        assert parse_bool("") is True  # Empty string != "false"

    def test_parse_bool_any_other_string(self):
        """Test parsing any other string"""
        assert parse_bool("yes") is True
        assert parse_bool("1") is True
        assert parse_bool("anything") is True

    def test_parse_bool_boolean_true(self):
        """Test parsing boolean True"""
        assert parse_bool(True) is True

    def test_parse_bool_boolean_false(self):
        """Test parsing boolean False"""
        assert (
            parse_bool(False) is False
        )  # str(False) == "False", which contains "false"

    def test_parse_bool_number(self):
        """Test parsing number"""
        assert parse_bool(0) is True
        assert parse_bool(1) is True


class TestParseGetParams:
    """Tests for parse_get_params function"""

    def test_parse_get_params_all_parameters(self):
        """Test parsing GET request with all parameters"""
        event = {
            "queryStringParameters": {
                "q": "temperature%20data",
                "spatial": "California",
                "temporal": "2020-01-01,2020-12-31",
                "embedding": "true",
                "pageNum": "2",
                "pageSize": "20",
                "search_params": "%7B%22key%22%3A%22value%22%7D",  # {"key":"value"}
            }
        }

        q, spatial, temporal, embedding, page_num, page_size, search_params = (
            parse_get_params(event)
        )

        assert q == "temperature data"
        assert spatial == "California"
        assert temporal == "2020-01-01,2020-12-31"
        assert embedding is True
        assert page_num == 2
        assert page_size == 20
        assert search_params == {"key": "value"}

    def test_parse_get_params_minimal_parameters(self):
        """Test parsing GET request with minimal parameters"""
        event = {"queryStringParameters": {}}

        q, spatial, temporal, embedding, page_num, page_size, search_params = (
            parse_get_params(event)
        )

        assert q == ""
        assert spatial == ""
        assert temporal == ""
        assert embedding is True
        assert page_num == 0
        assert page_size == 10
        assert search_params is None

    def test_parse_get_params_no_query_string_parameters(self):
        """Test parsing GET request with None queryStringParameters"""
        event = {"queryStringParameters": None}

        q, spatial, _, _, _, _, _ = parse_get_params(event)

        assert q == ""
        assert spatial == ""

    def test_parse_get_params_embedding_false(self):
        """Test parsing GET request with embedding=false"""
        event = {"queryStringParameters": {"q": "test", "embedding": "false"}}

        _, _, _, embedding, _, _, _ = parse_get_params(event)

        assert embedding is False

    def test_parse_get_params_invalid_search_params_json(self):
        """Test parsing GET request with invalid search_params JSON"""
        event = {"queryStringParameters": {"search_params": "not%20valid%20json"}}

        with pytest.raises(
            ValueError, match="search_params must be a valid JSON dictionary"
        ):
            parse_get_params(event)


class TestParsePostBody:
    """Tests for parse_post_body function"""

    def test_parse_post_body_json(self):
        """Test parsing POST body with JSON content type"""
        event = {
            "headers": {"content-type": "application/json"},
            "body": json.dumps(
                {
                    "q": "temperature data",
                    "spatial": "California",
                    "temporal": "2020-01-01,2020-12-31",
                    "embedding": True,
                    "pageNum": 2,
                    "pageSize": 20,
                    "search_params": {"key": "value"},
                }
            ),
        }

        q, spatial, _, embedding, _, _, search_params = parse_post_body(event)

        assert q == "temperature data"
        assert spatial == "California"
        assert embedding is True
        assert search_params == {"key": "value"}

    def test_parse_post_body_form_urlencoded(self):
        """Test parsing POST body with form-urlencoded content type"""
        event = {
            "headers": {"content-type": "application/x-www-form-urlencoded"},
            "body": "q=test+query&spatial=Texas&pageNum=1&pageSize=5",
        }

        q, spatial, _, _, page_num, page_size, _ = parse_post_body(event)

        assert q == "test query"
        assert spatial == "Texas"
        assert page_num == 1
        assert page_size == 5

    def test_parse_post_body_form_urlencoded_base64(self):
        """Test parsing POST body with base64 encoded form data"""
        body_str = "q=test&spatial=California"
        encoded_body = base64.b64encode(body_str.encode()).decode()

        event = {
            "headers": {"content-type": "application/x-www-form-urlencoded"},
            "body": encoded_body,
            "isBase64Encoded": True,
        }

        q, spatial, _, _, _, _, _ = parse_post_body(event)

        assert q == "test"
        assert spatial == "California"

    def test_parse_post_body_empty_body(self):
        """Test parsing POST with empty body"""
        event = {"headers": {"content-type": "application/json"}, "body": ""}

        q, spatial, _, _, _, _, _ = parse_post_body(event)

        assert q == ""
        assert spatial == ""

    def test_parse_post_body_invalid_json(self):
        """Test parsing POST with invalid JSON"""
        event = {
            "headers": {"content-type": "application/json"},
            "body": "not valid json {",
        }

        with pytest.raises(ValueError, match="Invalid JSON in request body"):
            parse_post_body(event)

    def test_parse_post_body_form_with_arrays(self):
        """Test parsing POST form with array notation"""
        body_str = (
            "search_params[options][temporal][]=2020-01-01&"
            "search_params[options][temporal][]=2020-12-31"
        )
        event = {
            "headers": {"content-type": "application/x-www-form-urlencoded"},
            "body": body_str,
        }

        _, _, _, _, _, _, search_params = parse_post_body(event)

        assert search_params is not None
        # The current implementation creates nested structure like "options[temporal]" as key
        # rather than nested objects
        assert any("options" in key for key in search_params.keys())

    def test_parse_post_body_form_without_array_notation(self):
        """Test parsing POST form with bracket notation but no array []"""
        event = {
            "headers": {"content-type": "application/x-www-form-urlencoded"},
            "body": "search_params[key]=value&search_params[other]=data",
        }

        _, _, _, _, _, _, search_params = parse_post_body(event)

        assert search_params is not None
        assert "key" in search_params
        assert search_params["key"] == "value"

    def test_parse_post_body_form_complex_nested_structure(self):
        """Test parsing complex nested form structure with multiple levels"""
        body_str = (
            "search_params[options][temporal][start]=2020-01-01&"
            "search_params[options][spatial]=global"
        )
        event = {
            "headers": {"content-type": "application/x-www-form-urlencoded"},
            "body": body_str,
        }

        _, _, _, _, _, _, search_params = parse_post_body(event)

        assert search_params is not None

    def test_parse_post_body_default_content_type(self):
        """Test parsing POST with no content type defaults to JSON"""
        event = {"headers": {}, "body": json.dumps({"q": "test"})}

        q, _, _, _, _, _, _ = parse_post_body(event)

        assert q == "test"

    def test_parse_post_body_case_insensitive_headers(self):
        """Test that header names are case insensitive"""
        event = {
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"q": "test"}),
        }

        q, _, _, _, _, _, _ = parse_post_body(event)

        assert q == "test"

    def test_parse_post_body_form_deeply_nested_with_multiple_brackets(self):
        """Test parsing form with deeply nested brackets to trigger _parse_nested_key branch"""
        # Use a different top-level key (not search_params) with nested brackets
        # This ensures _parse_nested_key processes keys with multiple bracket levels
        body_str = "options[level1][level2]=value"
        event = {
            "headers": {"content-type": "application/x-www-form-urlencoded"},
            "body": body_str,
        }

        q, _, _, _, _, _, search_params = parse_post_body(event)

        assert q == ""
        assert search_params is None

    def test_parse_post_body_form_with_closing_bracket_only(self):
        """Test parsing form with closing bracket but no opening bracket"""
        # This tests the edge case where a key has ] but we want to ensure
        # _parse_nested_key handles edge cases properly (len(parts) <= 1)
        body_str = "key]=value"
        event = {
            "headers": {"content-type": "application/x-www-form-urlencoded"},
            "body": body_str,
        }

        q, _, _, _, _, _, _ = parse_post_body(event)

        # Should handle gracefully - key without [ is treated as simple key
        assert q == ""


class TestParseFormat:
    """Tests for parse_format function"""

    def test_parse_format_json(self):
        """Test parsing .json format"""
        assert parse_format("/search/collections.json") == "json"

    def test_parse_format_umm_json(self):
        """Test parsing .umm_json format"""
        assert parse_format("/search/collections.umm_json") == "umm_json"

    def test_parse_format_no_extension(self):
        """Test parsing path with no extension defaults to umm_json"""
        assert parse_format("/search/collections") == "umm_json"

    def test_parse_format_none_path(self):
        """Test parsing None path defaults to umm_json"""
        assert parse_format(None) == "umm_json"

    def test_parse_format_other_extension(self):
        """Test parsing path with other extension defaults to umm_json"""
        assert parse_format("/search/collections.xml") == "umm_json"


class TestParseRequestParameters:
    """Tests for parse_request_parameters function"""

    def test_parse_request_parameters_get(self):
        """Test parsing GET request"""
        event = {"httpMethod": "GET", "queryStringParameters": {"q": "test"}}

        result = parse_request_parameters(event)

        assert result[0] == "test"

    def test_parse_request_parameters_post(self):
        """Test parsing POST request"""
        event = {
            "httpMethod": "POST",
            "headers": {"content-type": "application/json"},
            "body": json.dumps({"q": "test"}),
        }

        result = parse_request_parameters(event)

        assert result[0] == "test"

    def test_parse_request_parameters_unsupported_method(self):
        """Test parsing unsupported HTTP method"""
        event = {"httpMethod": "PUT"}

        with pytest.raises(ValueError, match="Unsupported HTTP method"):
            parse_request_parameters(event)

    def test_parse_request_parameters_default_get(self):
        """Test that missing httpMethod defaults to GET"""
        event = {"queryStringParameters": {"q": "test"}}

        result = parse_request_parameters(event)

        assert result[0] == "test"


class TestCreateEmptyResponse:
    """Tests for create_empty_response function"""

    def test_create_empty_response_json(self):
        """Test creating empty response in json format"""
        result = create_empty_response("json")

        assert "feed" in result
        assert "entry" in result["feed"]
        assert result["feed"]["entry"] == []

    def test_create_empty_response_umm_json(self):
        """Test creating empty response in umm_json format"""
        result = create_empty_response("umm_json")

        assert "items" in result
        assert result["items"] == []

    def test_create_empty_response_other_format(self):
        """Test empty response with other format defaults to umm_json"""
        result = create_empty_response("xml")

        assert "items" in result
        assert result["items"] == []


class TestParseNestedKey:
    """Tests for _parse_nested_key function"""

    def test_parse_nested_key_with_empty_parts(self):
        """Test _parse_nested_key with empty list"""
        result = _parse_nested_key([])
        assert result is None

    def test_parse_nested_key_with_single_element(self):
        """Test _parse_nested_key with single element list"""
        result = _parse_nested_key(["key"])
        assert result is None

    def test_parse_nested_key_with_two_elements(self):
        """Test _parse_nested_key with two elements"""
        result = _parse_nested_key(["main", "nested]"])
        assert result == "nested"

    def test_parse_nested_key_with_multiple_nested_levels(self):
        """Test _parse_nested_key with deeply nested brackets"""
        result = _parse_nested_key(["main", "level1][level2]"])
        assert result == "level1[level2]"


class TestParseNestedBrackets:
    """Tests for parse_nested_brackets function"""

    def test_parse_nested_brackets_simple_key(self):
        """Test parsing simple key without brackets"""
        body = {}
        parse_nested_brackets("key", "value", body)

        assert body == {"key": "value"}

    def test_parse_nested_brackets_single_level(self):
        """Test parsing single level bracket notation"""
        body = {}
        parse_nested_brackets("search_params[key]", "value", body)

        assert body == {"search_params": {"key": "value"}}

    def test_parse_nested_brackets_multiple_levels(self):
        """Test parsing multiple levels of bracket notation"""
        body = {}
        parse_nested_brackets("search_params[options][temporal]", "2020", body)

        assert body == {"search_params": {"options": {"temporal": "2020"}}}

    def test_parse_nested_brackets_array_notation(self):
        """Test parsing array notation with []"""
        body = {}
        parse_nested_brackets("search_params[items][]", "value1", body)
        parse_nested_brackets("search_params[items][]", "value2", body)

        assert body == {"search_params": {"items": ["value1", "value2"]}}

    def test_parse_nested_brackets_convert_non_list_to_list(self):
        """Test non-list values converted to list with array notation"""
        body = {}
        # First set a regular value
        parse_nested_brackets("search_params[items]", "single_value", body)
        # Then try to use it as an array
        parse_nested_brackets("search_params[items][]", "new_value", body)

        # "single_value" should be converted to list with both values
        assert body["search_params"]["items"] == ["single_value", "new_value"]

    def test_parse_nested_brackets_deep_nesting(self):
        """Test parsing deeply nested bracket notation"""
        body = {}
        parse_nested_brackets("a[b][c][d][e]", "value", body)

        assert body == {"a": {"b": {"c": {"d": {"e": "value"}}}}}

    def test_parse_nested_brackets_multiple_keys(self):
        """Test parsing multiple keys in same structure"""
        body = {}
        parse_nested_brackets("search_params[key1]", "value1", body)
        parse_nested_brackets("search_params[key2]", "value2", body)

        assert body == {"search_params": {"key1": "value1", "key2": "value2"}}

    def test_parse_nested_brackets_overwrite_existing(self):
        """Test that existing non-array values can be overwritten"""
        body = {}
        parse_nested_brackets("search_params[key]", "value1", body)
        parse_nested_brackets("search_params[key]", "value2", body)

        assert body == {"search_params": {"key": "value2"}}
