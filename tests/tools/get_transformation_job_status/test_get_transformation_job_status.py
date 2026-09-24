"""Tests for the get_transformation_job_status MCP tool."""

import importlib
import types
from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from models.tools.get_transformation_job_status import GetTransformationJobStatusOutput
from util.pagination import decode_cursor, encode_cursor

_CURSOR_BACKEND = "harmony_job_status"

# Mock payload based on the Harmony API response.
# Note: job_id, links, total_hits, and next_cursor are intentionally NOT included
# here — the real Harmony status endpoint doesn't return these; the tool sets them
# explicitly after parsing (job_id from the input param, links/total_hits/next_cursor
# derived from client.result_urls()).
MOCK_STATUS_RESPONSE = {
    "status": "successful",
    "message": "The job has completed successfully",
    "progress": 100,
    "created_at": "2026-09-18T00:10:10.444000Z",
    "updated_at": "2026-09-18T00:38:11.770000Z",
    "created_at_local": "2026-09-17T20:10:10-04:00",
    "updated_at_local": "2026-09-17T20:38:11-04:00",
    "request": "https://harmony.earthdata.nasa.gov/...",
    "num_input_granules": 2000,
    "data_expiration": "2026-10-18T00:10:10.444000Z",
    "data_expiration_local": "2026-10-17T20:10:10-04:00",
}

MOCK_RESULT_URLS = ["https://harmony.earthdata.nasa.gov/service-results/..."]


def _load_tool() -> types.ModuleType:
    """Load the tool module dynamically to avoid circular imports."""
    return importlib.import_module("tools.get_transformation_job_status.tool")


def _make_link(n: int) -> str:
    return f"https://harmony.earthdata.nasa.gov/service-results/result-{n}.nc"


@pytest.fixture
def mock_get_access_token() -> Generator[MagicMock, None, None]:
    """Mock the get_access_token function specifically within the tool module."""
    with patch("tools.get_transformation_job_status.tool.get_access_token") as mock_token_func:
        mock_token_obj = MagicMock()
        mock_token_obj.token = "fake-jwt-token"
        mock_token_func.return_value = mock_token_obj
        yield mock_token_func


@pytest.fixture
def mock_get_client() -> Generator[MagicMock, None, None]:
    """Mock util.harmony.client.get_client within the tool."""
    with patch("tools.get_transformation_job_status.tool.get_client") as mock_client:
        yield mock_client


def test_get_transformation_job_status_success(
    mock_get_client: MagicMock,
    mock_get_access_token: MagicMock,
) -> None:
    """Test successful retrieval of job status, including result links for a terminal job.

    result_urls is mocked as a generator (as it is in the real client) to guard
    against regressions like the earlier `len()`-on-generator bug.
    """
    tool = _load_tool()

    mock_client_instance = MagicMock()
    mock_get_client.return_value = mock_client_instance
    mock_client_instance.status.return_value = MOCK_STATUS_RESPONSE
    mock_client_instance.result_urls.return_value = iter(MOCK_RESULT_URLS)

    job_id = "test-job-12345"
    result = tool.get_transformation_job_status(job_id=job_id)

    expected_output = GetTransformationJobStatusOutput(**MOCK_STATUS_RESPONSE)
    expected_output.job_id = job_id
    expected_output.links = MOCK_RESULT_URLS
    expected_output.total_hits = len(MOCK_RESULT_URLS)
    expected_output.next_cursor = None
    expected = expected_output.model_dump(mode="json", by_alias=True)

    assert result == expected
    assert result["status"] == "successful"
    mock_get_access_token.assert_called_once()
    mock_get_client.assert_called_once_with("fake-jwt-token")
    mock_client_instance.status.assert_called_once_with(job_id)
    mock_client_instance.result_urls.assert_called_once_with(job_id)


def test_get_transformation_job_status_non_terminal_skips_result_urls(
    mock_get_client: MagicMock,
    mock_get_access_token: MagicMock,
) -> None:
    """Result URLs should not be fetched for a job that hasn't finished yet."""
    tool = _load_tool()

    mock_client_instance = MagicMock()
    mock_get_client.return_value = mock_client_instance
    running_status = {**MOCK_STATUS_RESPONSE, "status": "running", "message": "The job is being processed", "progress": 42}
    mock_client_instance.status.return_value = running_status

    result = tool.get_transformation_job_status(job_id="test-job-12345")

    mock_client_instance.result_urls.assert_not_called()
    assert result.get("links") == []
    assert result.get("total_hits") == 0
    assert result.get("next_cursor") is None


def test_get_transformation_job_status_pagination_first_page(
    mock_get_client: MagicMock,
    mock_get_access_token: MagicMock,
) -> None:
    """First page returns limit items, next_cursor is set, total_hits is full count."""
    tool = _load_tool()
    all_links = [_make_link(i) for i in range(15)]

    mock_client_instance = MagicMock()
    mock_get_client.return_value = mock_client_instance
    mock_client_instance.status.return_value = MOCK_STATUS_RESPONSE
    mock_client_instance.result_urls.side_effect = lambda job_id: iter(all_links)

    job_id = "test-job-page1"
    result = tool.get_transformation_job_status(job_id=job_id, limit=10)

    assert result["total_hits"] == 15
    assert len(result["links"]) == 10
    assert result["links"][0] == all_links[0]
    assert result["links"][9] == all_links[9]
    assert result["next_cursor"] is not None

    parsed = decode_cursor(result["next_cursor"])
    assert parsed["backend"] == _CURSOR_BACKEND
    assert isinstance(parsed["value"], dict)
    assert parsed["value"]["offset"] == 10
    assert parsed["value"]["job_id"] == job_id


def test_get_transformation_job_status_pagination_second_page(
    mock_get_client: MagicMock,
    mock_get_access_token: MagicMock,
) -> None:
    """A pre-built cursor resumes at the correct offset and returns remaining items."""
    tool = _load_tool()
    all_links = [_make_link(i) for i in range(15)]

    mock_client_instance = MagicMock()
    mock_get_client.return_value = mock_client_instance
    mock_client_instance.status.return_value = MOCK_STATUS_RESPONSE
    mock_client_instance.result_urls.side_effect = lambda job_id: iter(all_links)

    job_id = "test-job-page2"
    cursor = encode_cursor(_CURSOR_BACKEND, {"offset": 10, "job_id": job_id})
    result = tool.get_transformation_job_status(job_id=job_id, limit=10, cursor=cursor)

    assert result["total_hits"] == 15
    assert len(result["links"]) == 5
    assert result["links"][0] == all_links[10]
    assert result["links"][4] == all_links[14]
    assert result["next_cursor"] is None


def test_get_transformation_job_status_pagination_exact_multiple(
    mock_get_client: MagicMock,
    mock_get_access_token: MagicMock,
) -> None:
    """When total is an exact multiple of limit, the final page has next_cursor=None."""
    tool = _load_tool()
    all_links = [_make_link(i) for i in range(10)]

    mock_client_instance = MagicMock()
    mock_get_client.return_value = mock_client_instance
    mock_client_instance.status.return_value = MOCK_STATUS_RESPONSE
    mock_client_instance.result_urls.side_effect = lambda job_id: iter(all_links)

    job_id = "test-job-exact"
    cursor = encode_cursor(_CURSOR_BACKEND, {"offset": 10, "job_id": job_id})
    result = tool.get_transformation_job_status(job_id=job_id, limit=10, cursor=cursor)

    assert result["total_hits"] == 10
    assert result["links"] == []
    assert result["next_cursor"] is None


def test_get_transformation_job_status_invalid_cursor(
    mock_get_client: MagicMock,
    mock_get_access_token: MagicMock,
) -> None:
    """Garbage cursor returns a clean error response, not an unhandled exception."""
    tool = _load_tool()

    mock_client_instance = MagicMock()
    mock_get_client.return_value = mock_client_instance

    result = tool.get_transformation_job_status(job_id="test-job", cursor="not-valid-base64!!!")

    assert result.get("code") == "ValueError"
    assert "cursor" in result.get("description", "").lower()
    mock_client_instance.status.assert_not_called()


def test_get_transformation_job_status_cross_backend_cursor(
    mock_get_client: MagicMock,
    mock_get_access_token: MagicMock,
) -> None:
    """A cursor minted by a different tool's backend namespace must be rejected."""
    tool = _load_tool()

    mock_client_instance = MagicMock()
    mock_get_client.return_value = mock_client_instance

    foreign_cursor = encode_cursor("kms", {"offset": 10, "query": "ocean"})
    result = tool.get_transformation_job_status(job_id="test-job", cursor=foreign_cursor)

    assert result.get("code") == "ValueError"
    assert "cannot be reused across" in result.get("description", "").lower()
    mock_client_instance.status.assert_not_called()


def test_get_transformation_job_status_old_format_cursor_returns_error(
    mock_get_client: MagicMock,
    mock_get_access_token: MagicMock,
) -> None:
    """An old-format (scalar, non-dict) cursor value must return a clean error."""
    tool = _load_tool()

    mock_client_instance = MagicMock()
    mock_get_client.return_value = mock_client_instance

    old_cursor = encode_cursor(_CURSOR_BACKEND, 10)
    result = tool.get_transformation_job_status(job_id="test-job", cursor=old_cursor)

    assert result.get("code") == "ValueError"
    assert "cursor" in result.get("description", "").lower()
    mock_client_instance.status.assert_not_called()


def test_get_transformation_job_status_cursor_rejects_changed_job_id(
    mock_get_client: MagicMock,
    mock_get_access_token: MagicMock,
) -> None:
    """A cursor minted for one job_id must be rejected if reused with a different job_id."""
    tool = _load_tool()

    mock_client_instance = MagicMock()
    mock_get_client.return_value = mock_client_instance

    cursor = encode_cursor(_CURSOR_BACKEND, {"offset": 10, "job_id": "job-A"})
    result = tool.get_transformation_job_status(job_id="job-B", limit=10, cursor=cursor)

    assert result.get("code") == "CursorScopeError"
    assert "job-scoped" in result.get("description", "").lower()
    mock_client_instance.status.assert_not_called()
    mock_client_instance.result_urls.assert_not_called()


def test_get_transformation_job_status_calls_trace_update(
    mock_get_client: MagicMock,
    mock_get_access_token: MagicMock,
) -> None:
    """Test telemetry tracing is called correctly."""
    tool = _load_tool()

    mock_client_instance = MagicMock()
    mock_get_client.return_value = mock_client_instance
    mock_client_instance.status.return_value = {}

    with patch.object(tool, "trace_update") as mock_trace_update:
        tool.get_transformation_job_status(job_id="test-job")

    assert mock_trace_update.called


def test_get_transformation_job_status_validation_error() -> None:
    """Test behavior when input validation fails (e.g., job_id is missing/None)."""
    tool = _load_tool()

    result = tool.get_transformation_job_status(job_id=None)

    assert result.get("code") in ["ValueError", "ValidationError"]
    assert "job_id" in result.get("description", "").lower()


def test_get_transformation_job_status_client_error(
    mock_get_client: MagicMock,
    mock_get_access_token: MagicMock,
) -> None:
    """Test behavior when the Harmony API client raises an exception, including the
    common case of Harmony's own descriptive error (e.g., invalid/missing job_id).
    """
    tool = _load_tool()

    mock_client_instance = MagicMock()
    mock_get_client.return_value = mock_client_instance
    mock_client_instance.status.side_effect = Exception("Job test-job-123 not found")

    result = tool.get_transformation_job_status(job_id="test-job-123")

    assert result.get("code") == "Exception"
    assert "Failed to fetch job status from Harmony: Job test-job-123 not found" in result.get(
        "description", ""
    )


def test_get_transformation_job_status_schema_mismatch(
    mock_get_client: MagicMock,
    mock_get_access_token: MagicMock,
) -> None:
    """Test behavior when Harmony's status response doesn't match the expected schema.

    Uses a non-terminal status so result_urls is never invoked, isolating this test
    to the final GetTransformationJobStatusOutput(**status) parsing step specifically.
    """
    tool = _load_tool()

    mock_client_instance = MagicMock()
    mock_get_client.return_value = mock_client_instance
    malformed_status = {
        **MOCK_STATUS_RESPONSE,
        "status": "running",
        "progress": "not-a-number",
    }
    mock_client_instance.status.return_value = malformed_status

    result = tool.get_transformation_job_status(job_id="test-job-malformed")

    assert result.get("code") in ["ValueError", "ValidationError"]
    assert "Unexpected response shape from Harmony" in result.get("description", "")
    mock_client_instance.result_urls.assert_not_called()


def test_get_transformation_job_status_fields_filter(
    mock_get_client: MagicMock,
    mock_get_access_token: MagicMock,
) -> None:
    """fields parameter strips unrequested top-level keys, keeping mandatory ones."""
    tool = _load_tool()

    mock_client_instance = MagicMock()
    mock_get_client.return_value = mock_client_instance
    mock_client_instance.status.return_value = MOCK_STATUS_RESPONSE
    mock_client_instance.result_urls.return_value = iter(MOCK_RESULT_URLS)

    result = tool.get_transformation_job_status(job_id="test-job-fields", fields=["request"])

    # Mandatory fields always present regardless of the fields filter.
    assert "job_id" in result
    assert "status" in result
    assert "message" in result
    assert "progress" in result
    assert "total_hits" in result
    assert "next_cursor" in result

    # Requested field present.
    assert "request" in result

    # Non-mandatory, non-requested fields stripped.
    assert "links" not in result
    assert "created_at" not in result
    assert "updated_at" not in result
    assert "num_input_granules" not in result
    assert "data_expiration" not in result
