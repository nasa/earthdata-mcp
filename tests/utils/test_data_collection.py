"""Tests for data_collection module"""

from unittest.mock import patch, Mock
import pytest
import requests
from util.data_collection import fetch_cmr_data


class TestFetchCmrData:
    """Tests for fetch_cmr_data function"""

    @patch("util.data_collection.requests.get")
    def test_successful_get_request_with_json_response(self, mock_get):
        """Test successful GET request with JSON response"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "test"}
        mock_response.headers = {"Content-Type": "application/json"}
        mock_get.return_value = mock_response

        result = fetch_cmr_data(
            cmr_url="https://cmr.earthdata.nasa.gov/search/collections",
            method="GET",
            params={"keyword": "test"},
        )

        assert result["success"] is True
        assert result["status_code"] == 200
        assert result["data"] == {"data": "test"}
        assert "headers" in result

    @patch("util.data_collection.requests.get")
    def test_successful_get_request_with_text_response(self, mock_get):
        """Test successful GET request with text response"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Not JSON")
        mock_response.text = "Plain text response"
        mock_response.headers = {"Content-Type": "text/plain"}
        mock_get.return_value = mock_response

        result = fetch_cmr_data(
            cmr_url="https://cmr.earthdata.nasa.gov/search/collections", method="GET"
        )

        assert result["success"] is True
        assert result["status_code"] == 200
        assert result["data"] == "Plain text response"

    @patch("util.data_collection.requests.post")
    def test_successful_post_request(self, mock_post):
        """Test successful POST request"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"created": True}
        mock_response.headers = {"Content-Type": "application/json"}
        mock_post.return_value = mock_response

        result = fetch_cmr_data(
            cmr_url="https://cmr.earthdata.nasa.gov/search/collections",
            method="POST",
            data={"key": "value"},
        )

        assert result["success"] is True
        assert result["status_code"] == 200
        assert result["data"] == {"created": True}

    @patch("util.data_collection.requests.get")
    def test_get_request_with_search_after_header(self, mock_get):
        """Test GET request with search_after header"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "test"}
        mock_response.headers = {}
        mock_get.return_value = mock_response

        _ = fetch_cmr_data(
            cmr_url="https://cmr.earthdata.nasa.gov/search/collections",
            method="GET",
            search_after="abc123",
        )

        # Verify the header was added
        call_kwargs = mock_get.call_args[1]
        assert "CMR-Search-After" in call_kwargs["headers"]
        assert call_kwargs["headers"]["CMR-Search-After"] == "abc123"

    @patch("util.data_collection.requests.get")
    def test_get_request_with_custom_headers(self, mock_get):
        """Test GET request with custom headers"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "test"}
        mock_response.headers = {}
        mock_get.return_value = mock_response

        custom_headers = {"Authorization": "Bearer token123"}
        _ = fetch_cmr_data(
            cmr_url="https://cmr.earthdata.nasa.gov/search/collections",
            method="GET",
            headers=custom_headers,
        )

        # Verify custom headers were included
        call_kwargs = mock_get.call_args[1]
        assert "Authorization" in call_kwargs["headers"]
        assert call_kwargs["headers"]["Authorization"] == "Bearer token123"
        # Default header should also be present
        assert call_kwargs["headers"]["Client-Id"] == "cmr-nlp-search"

    @patch("util.data_collection.requests.post")
    def test_post_request_with_files(self, mock_post):
        """Test POST request with files"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"uploaded": True}
        mock_response.headers = {}
        mock_post.return_value = mock_response

        files = {"file": ("test.txt", "file content")}
        result = fetch_cmr_data(
            cmr_url="https://cmr.earthdata.nasa.gov/upload", method="POST", files=files
        )

        assert result["success"] is True
        call_kwargs = mock_post.call_args[1]
        assert "files" in call_kwargs

    def test_unsupported_http_method(self):
        """Test error handling for unsupported HTTP method"""
        # ValueError is not caught, so it will raise
        with pytest.raises(ValueError, match="Unsupported HTTP method: DELETE"):
            fetch_cmr_data(
                cmr_url="https://cmr.earthdata.nasa.gov/search/collections",
                method="DELETE",
            )

    @patch("util.data_collection.requests.get")
    def test_non_200_status_code_with_json_error(self, mock_get):
        """Test handling non-200 status code with JSON error response"""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.reason = "Not Found"
        mock_response.json.return_value = {"error": "Resource not found"}
        mock_response.headers = {}

        # Create an HTTPError with the response attached
        http_error = requests.exceptions.HTTPError()
        http_error.response = mock_response
        mock_response.raise_for_status.side_effect = http_error
        mock_get.return_value = mock_response

        result = fetch_cmr_data(
            cmr_url="https://cmr.earthdata.nasa.gov/search/collections", method="GET"
        )

        # HTTPError is caught by RequestException handler
        assert result["success"] is False
        assert result["status_code"] == 404
        assert "error" in result

    @patch("util.data_collection.requests.get")
    def test_non_200_status_code_with_text_error(self, mock_get):
        """Test handling non-200 status code with text error response"""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.reason = "Internal Server Error"
        mock_response.json.side_effect = ValueError("Not JSON")
        mock_response.text = "Server error occurred"
        mock_response.headers = {}

        # Create an HTTPError with the response attached
        http_error = requests.exceptions.HTTPError()
        http_error.response = mock_response
        mock_response.raise_for_status.side_effect = http_error
        mock_get.return_value = mock_response

        result = fetch_cmr_data(
            cmr_url="https://cmr.earthdata.nasa.gov/search/collections", method="GET"
        )

        # HTTPError is caught by RequestException handler
        assert result["success"] is False
        assert result["status_code"] == 500
        assert "error" in result
        assert result["data"] is None

    @patch("util.data_collection.requests.get")
    def test_request_exception_with_response(self, mock_get):
        """Test handling request exception with response object"""
        mock_response = Mock()
        mock_response.status_code = 503
        mock_response.headers = {"Retry-After": "60"}

        exception = requests.exceptions.ConnectionError("Connection failed")
        exception.response = mock_response
        mock_get.side_effect = exception

        result = fetch_cmr_data(
            cmr_url="https://cmr.earthdata.nasa.gov/search/collections", method="GET"
        )

        assert result["success"] is False
        assert result["status_code"] == 503
        assert "error" in result
        assert "Connection failed" in result["error"]

    @patch("util.data_collection.requests.get")
    def test_request_exception_without_response(self, mock_get):
        """Test handling request exception without response object"""
        exception = requests.exceptions.Timeout("Request timed out")
        mock_get.side_effect = exception

        result = fetch_cmr_data(
            cmr_url="https://cmr.earthdata.nasa.gov/search/collections", method="GET"
        )

        assert result["success"] is False
        assert result["status_code"] == 500
        assert "error" in result
        assert "Request timed out" in result["error"]

    @patch("util.data_collection.requests.get")
    def test_timeout_parameter(self, mock_get):
        """Test that timeout is set correctly"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "test"}
        mock_response.headers = {}
        mock_get.return_value = mock_response

        fetch_cmr_data(
            cmr_url="https://cmr.earthdata.nasa.gov/search/collections", method="GET"
        )

        call_kwargs = mock_get.call_args[1]
        assert "timeout" in call_kwargs
        assert call_kwargs["timeout"] == 60

    @patch("util.data_collection.requests.get")
    def test_default_client_id_header(self, mock_get):
        """Test that default Client-Id header is included"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "test"}
        mock_response.headers = {}
        mock_get.return_value = mock_response

        fetch_cmr_data(
            cmr_url="https://cmr.earthdata.nasa.gov/search/collections", method="GET"
        )

        call_kwargs = mock_get.call_args[1]
        assert call_kwargs["headers"]["Client-Id"] == "cmr-nlp-search"

    @patch("util.data_collection.requests.get")
    def test_non_200_status_without_raising(self, mock_get):
        """Test handling non-200 status code when raise_for_status doesn't raise"""
        mock_response = Mock()
        mock_response.status_code = 202  # Accepted, not 200
        mock_response.reason = "Accepted"
        mock_response.json.return_value = {"message": "Request accepted"}
        mock_response.headers = {"Content-Type": "application/json"}
        # Don't raise on raise_for_status for 202
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = fetch_cmr_data(
            cmr_url="https://cmr.earthdata.nasa.gov/search/collections", method="GET"
        )

        # This should hit the non-200 branch in the code
        assert result["success"] is False
        assert result["status_code"] == 202
        assert result["error"] == "HTTP 202: Accepted"
        assert result["data"] == {"message": "Request accepted"}

    @patch("util.data_collection.requests.get")
    def test_non_200_status_with_text_response_without_raising(self, mock_get):
        """Test handling non-200 status code with text response
        when raise_for_status doesn't raise"""
        mock_response = Mock()
        mock_response.status_code = 202  # Accepted, not 200
        mock_response.reason = "Accepted"
        mock_response.json.side_effect = ValueError("Not JSON")
        mock_response.text = "Plain text response"
        mock_response.headers = {"Content-Type": "text/plain"}
        # Don't raise on raise_for_status for 202
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = fetch_cmr_data(
            cmr_url="https://cmr.earthdata.nasa.gov/search/collections", method="GET"
        )

        # This should hit the non-200 branch with text fallback
        assert result["success"] is False
        assert result["status_code"] == 202
        assert result["error"] == "HTTP 202: Accepted"
        assert result["data"] == "Plain text response"
