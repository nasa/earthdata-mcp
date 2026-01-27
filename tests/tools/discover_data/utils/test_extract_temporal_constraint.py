"""Tests for extract_temporal_constraint implementation with mocked dependencies."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from tools.discover_data.input_model import TemporalConstraint
from tools.discover_data.utils import extract_temporal_constraint


@pytest.fixture(autouse=True)
def stub_langfuse(monkeypatch):
    """Disable real Langfuse initialization during tests."""
    monkeypatch.setattr("tools.discover_data.utils.extract_temporal_constraint.LANGFUSE", None)


class TestExtractTemporalWithLLM:
    """Test the _extract_temporal_with_llm helper function."""

    def test_successful_extraction(self):
        """LLM extraction should return TemporalConstraint with dates."""
        with (
            patch("tools.discover_data.utils.extract_temporal_constraint.instructor.from_provider") as mock_instructor,
            patch("tools.discover_data.utils.extract_temporal_constraint.load_extraction_prompt") as mock_prompt,
        ):
            # Mock the instructor client
            mock_client = MagicMock()
            mock_instructor.return_value = mock_client
            mock_prompt.return_value = "System prompt"

            # Create a mock response
            mock_response = MagicMock()
            mock_response.start_date = datetime(2024, 1, 1, tzinfo=UTC)
            mock_response.end_date = datetime(2024, 12, 31, tzinfo=UTC)
            mock_response.reasoning = "Full year 2024"
            mock_client.create.return_value = mock_response

            result = extract_temporal_constraint._extract_temporal_with_llm("data from 2024")

            assert result.start_date == datetime(2024, 1, 1, tzinfo=UTC)
            assert result.end_date == datetime(2024, 12, 31, tzinfo=UTC)
            assert result.reasoning == "Full year 2024"
            mock_instructor.assert_called_once()

    def test_partial_extraction(self):
        """LLM extraction should handle partial date extraction."""
        with (
            patch("tools.discover_data.utils.extract_temporal_constraint.instructor.from_provider") as mock_instructor,
            patch("tools.discover_data.utils.extract_temporal_constraint.load_extraction_prompt") as mock_prompt,
        ):
            mock_client = MagicMock()
            mock_instructor.return_value = mock_client
            mock_prompt.return_value = "System prompt"

            mock_response = MagicMock()
            mock_response.start_date = datetime(2024, 1, 1, tzinfo=UTC)
            mock_response.end_date = None
            mock_response.reasoning = "Only start date found"
            mock_client.create.return_value = mock_response

            result = extract_temporal_constraint._extract_temporal_with_llm("data from 2024 onwards")

            assert result.start_date == datetime(2024, 1, 1, tzinfo=UTC)
            assert result.end_date is None

    def test_llm_error_propagates(self):
        """LLM extraction should propagate errors from LLM."""
        with (
            patch("tools.discover_data.utils.extract_temporal_constraint.instructor.from_provider") as mock_instructor,
            patch("tools.discover_data.utils.extract_temporal_constraint.load_extraction_prompt") as mock_prompt,
        ):
            mock_client = MagicMock()
            mock_instructor.return_value = mock_client
            mock_prompt.return_value = "System prompt"
            mock_client.create.side_effect = ValueError("LLM API error")

            with pytest.raises(RuntimeError, match="Failed to extract temporal ranges from query"):
                extract_temporal_constraint._extract_temporal_with_llm("invalid query")


class TestExtractTemporalConstraintWrapper:
    """Test the extract_temporal_constraint wrapper function."""

    def test_successful_extraction_with_mock(self):
        """Wrapper should delegate to _extract_temporal_with_llm successfully."""
        with patch("tools.discover_data.utils.extract_temporal_constraint._extract_temporal_with_llm") as mock_llm:
            mock_result = TemporalConstraint(
                start_date=datetime(2024, 1, 1, tzinfo=UTC),
                end_date=datetime(2024, 12, 31, tzinfo=UTC),
                reasoning="Year 2024",
            )
            mock_llm.return_value = mock_result

            result = extract_temporal_constraint.extract_temporal_constraint("data from 2024")

            assert result.start_date == datetime(2024, 1, 1, tzinfo=UTC)
            assert result.end_date == datetime(2024, 12, 31, tzinfo=UTC)
            mock_llm.assert_called_once_with("data from 2024")

    def test_empty_query_returns_neutral(self):
        """Empty query should return neutral constraint without LLM call."""
        with patch("tools.discover_data.utils.extract_temporal_constraint._extract_temporal_with_llm") as mock_llm:
            result = extract_temporal_constraint.extract_temporal_constraint("")

            assert result.start_date is None
            assert result.end_date is None
            assert result.reasoning == "No temporal information found in query"
            mock_llm.assert_not_called()

    def test_none_query_returns_neutral(self):
        """None query should return neutral constraint without LLM call."""
        with patch("tools.discover_data.utils.extract_temporal_constraint._extract_temporal_with_llm") as mock_llm:
            result = extract_temporal_constraint.extract_temporal_constraint(None)

            assert result.start_date is None
            assert result.end_date is None
            assert result.reasoning == "No temporal information found in query"
            mock_llm.assert_not_called()

    def test_whitespace_only_query_passes_to_llm(self):
        """Whitespace-only query should pass to LLM."""
        with patch("tools.discover_data.utils.extract_temporal_constraint._extract_temporal_with_llm") as mock_llm:
            mock_llm.return_value = TemporalConstraint(
                start_date=None,
                end_date=None,
                reasoning="No temporal data",
            )

            extract_temporal_constraint.extract_temporal_constraint("   ")

            mock_llm.assert_called_once_with("   ")


class TestExtractTemporalInitialization:
    """Test module-level initialization and error handling."""

    def test_instructor_client_initialization_error(self):
        """Instructor client initialization failure should be caught."""
        with (
            patch("tools.discover_data.utils.extract_temporal_constraint.instructor.from_provider") as mock_instructor,
            patch("tools.discover_data.utils.extract_temporal_constraint.LANGFUSE", None),
        ):
            mock_instructor.side_effect = RuntimeError("Bedrock service unavailable")

            with pytest.raises(RuntimeError, match="Failed to initialize instructor client"):
                extract_temporal_constraint._extract_temporal_with_llm("test query")

    def test_langfuse_error_handling_when_available(self):
        """When Langfuse is available, errors should be logged to it."""
        with (
            patch("tools.discover_data.utils.extract_temporal_constraint.instructor.from_provider") as mock_instructor,
            patch("tools.discover_data.utils.extract_temporal_constraint.LANGFUSE") as mock_langfuse,
        ):
            mock_langfuse.update_current_trace = MagicMock()
            mock_instructor.side_effect = ValueError("Bedrock error")

            with pytest.raises(RuntimeError, match="Failed to initialize instructor client"):
                extract_temporal_constraint._extract_temporal_with_llm("test query")

            # Verify Langfuse was called to log the error
            assert mock_langfuse.update_current_trace.called

    def test_empty_query_returns_no_constraint(self):
        """Empty query should return TemporalConstraint with no dates."""
        result = extract_temporal_constraint.extract_temporal_constraint("")

        assert result.start_date is None
        assert result.end_date is None
        assert result.reasoning == "No temporal information found in query"

    def test_llm_error_with_langfuse_logging(self):
        """LLM errors should log to Langfuse when available."""
        with (
            patch("tools.discover_data.utils.extract_temporal_constraint.instructor.from_provider") as mock_instructor,
            patch("tools.discover_data.utils.extract_temporal_constraint.load_extraction_prompt") as mock_prompt,
            patch("tools.discover_data.utils.extract_temporal_constraint.LANGFUSE") as mock_langfuse,
        ):
            mock_client = MagicMock()
            mock_instructor.return_value = mock_client
            mock_prompt.return_value = "System prompt"
            mock_client.create.side_effect = ValueError("LLM API failed")
            mock_langfuse.update_current_trace = MagicMock()

            with pytest.raises(RuntimeError, match="Failed to extract temporal ranges"):
                extract_temporal_constraint._extract_temporal_with_llm("test query")

            # Verify Langfuse was called with error tags
            assert mock_langfuse.update_current_trace.called

    def test_successful_extraction_logs_to_langfuse(self):
        """Successful extraction should log success to Langfuse when available."""
        with (
            patch("tools.discover_data.utils.extract_temporal_constraint.instructor.from_provider") as mock_instructor,
            patch("tools.discover_data.utils.extract_temporal_constraint.load_extraction_prompt") as mock_prompt,
            patch("tools.discover_data.utils.extract_temporal_constraint.LANGFUSE") as mock_langfuse,
        ):
            mock_client = MagicMock()
            mock_instructor.return_value = mock_client
            mock_prompt.return_value = "System prompt"

            mock_response = MagicMock()
            mock_response.start_date = datetime(2024, 1, 1, tzinfo=UTC)
            mock_response.end_date = datetime(2024, 12, 31, tzinfo=UTC)
            mock_response.reasoning = "Year 2024"
            mock_client.create.return_value = mock_response
            mock_langfuse.update_current_trace = MagicMock()

            result = extract_temporal_constraint._extract_temporal_with_llm("2024 data")

            assert result.start_date == datetime(2024, 1, 1, tzinfo=UTC)
            # Verify success was logged to Langfuse
            assert mock_langfuse.update_current_trace.called
