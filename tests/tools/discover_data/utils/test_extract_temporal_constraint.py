"""Tests for extract_temporal_constraint implementation with mocked dependencies."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from tools.discover_data.utils import extract_temporal_constraint


class TestExtractTemporalWithLLM:
    """Test the extract_temporal_constraint helper function."""

    def test_successful_extraction(self, mock_temporal_llm_dependencies):
        """LLM extraction should return TemporalConstraint with dates."""
        mock_instructor, mock_client, _ = mock_temporal_llm_dependencies

        mock_response = MagicMock()
        mock_response.start_date = datetime(2024, 1, 1, tzinfo=UTC)
        mock_response.end_date = datetime(2024, 12, 31, tzinfo=UTC)
        mock_response.reasoning = "Full year 2024"
        mock_client.create.return_value = mock_response

        result = extract_temporal_constraint.extract_temporal_constraint("data from 2024")

        assert result.start_date == datetime(2024, 1, 1, tzinfo=UTC)
        assert result.end_date == datetime(2024, 12, 31, tzinfo=UTC)
        assert result.reasoning == "Full year 2024"
        mock_instructor.assert_called_once()

    def test_partial_extraction(self, mock_temporal_llm_dependencies):
        """LLM extraction should handle partial date extraction."""
        _, mock_client, _ = mock_temporal_llm_dependencies

        mock_response = MagicMock()
        mock_response.start_date = datetime(2024, 1, 1, tzinfo=UTC)
        mock_response.end_date = None
        mock_response.reasoning = "Only start date found"
        mock_client.create.return_value = mock_response

        result = extract_temporal_constraint.extract_temporal_constraint("data from 2024 onwards")

        assert result.start_date == datetime(2024, 1, 1, tzinfo=UTC)
        assert result.end_date is None

    def test_llm_error_propagates(self, mock_temporal_llm_dependencies):
        """LLM extraction should propagate errors from LLM."""
        _, mock_client, _ = mock_temporal_llm_dependencies
        mock_client.create.side_effect = ValueError("LLM API error")

        with pytest.raises(RuntimeError, match="Failed to extract temporal ranges from query"):
            extract_temporal_constraint.extract_temporal_constraint("invalid query")


class TestExtractTemporalConstraintEdgeCases:
    """Test edge cases for extract_temporal_constraint."""

    def test_empty_query_returns_neutral(self):
        """Empty query should return neutral constraint without LLM call."""
        result = extract_temporal_constraint.extract_temporal_constraint("")

        assert result.start_date is None
        assert result.end_date is None
        assert result.reasoning == "No temporal information found in query"

    def test_none_query_returns_neutral(self):
        """None query should return neutral constraint without LLM call."""
        result = extract_temporal_constraint.extract_temporal_constraint(None)

        assert result.start_date is None
        assert result.end_date is None
        assert result.reasoning == "No temporal information found in query"


class TestExtractTemporalInitialization:
    """Test module-level initialization and error handling."""

    def test_instructor_client_initialization_error(self):
        """Instructor client initialization failure should be caught."""
        with patch(
            "tools.discover_data.utils.extract_temporal_constraint.instructor.from_provider"
        ) as mock_instructor:
            mock_instructor.side_effect = RuntimeError("Bedrock service unavailable")

            with pytest.raises(RuntimeError, match="Failed to initialize instructor client"):
                extract_temporal_constraint.extract_temporal_constraint("test query")

    def test_langfuse_error_handling_when_available(self):
        """When Langfuse is available, errors should be logged via trace_update."""
        with (
            patch(
                "tools.discover_data.utils.extract_temporal_constraint.instructor.from_provider"
            ) as mock_instructor,
            patch(
                "tools.discover_data.utils.extract_temporal_constraint.trace_update"
            ) as mock_trace,
        ):
            mock_instructor.side_effect = ValueError("Bedrock error")

            with pytest.raises(RuntimeError, match="Failed to initialize instructor client"):
                extract_temporal_constraint.extract_temporal_constraint("test query")

            assert mock_trace.called

    def test_llm_error_with_langfuse_logging(self, mock_temporal_llm_dependencies):
        """LLM errors should log via trace_update."""
        _, mock_client, _ = mock_temporal_llm_dependencies
        mock_client.create.side_effect = ValueError("LLM API failed")

        with patch(
            "tools.discover_data.utils.extract_temporal_constraint.trace_update"
        ) as mock_trace:
            with pytest.raises(RuntimeError, match="Failed to extract temporal ranges"):
                extract_temporal_constraint.extract_temporal_constraint("test query")

            assert mock_trace.called

    def test_successful_extraction_logs_to_langfuse(self, mock_temporal_llm_dependencies):
        """Successful extraction should log success via trace_update."""
        _, mock_client, _ = mock_temporal_llm_dependencies

        mock_response = MagicMock()
        mock_response.start_date = datetime(2024, 1, 1, tzinfo=UTC)
        mock_response.end_date = datetime(2024, 12, 31, tzinfo=UTC)
        mock_response.reasoning = "Year 2024"
        mock_client.create.return_value = mock_response

        with patch(
            "tools.discover_data.utils.extract_temporal_constraint.trace_update"
        ) as mock_trace:
            result = extract_temporal_constraint.extract_temporal_constraint("2024 data")

            assert result.start_date == datetime(2024, 1, 1, tzinfo=UTC)
            assert mock_trace.called
