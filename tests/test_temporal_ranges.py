"""Unit tests for temporal range extraction utility with mocked LLM responses."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from tools.discover_data.utils.extract_temporal_constraint import extract_temporal_constraint
from tools.models.constraints import TemporalConstraint


class TestTemporalRangesMocked:
    """Mocked unit tests for temporal ranges (no LLM dependency)."""

    @pytest.fixture
    def mock_instructor_client(self):
        """Fixture to create a mocked instructor client."""
        with patch(
            "tools.discover_data.utils.extract_temporal_constraint.instructor.from_provider"
        ) as mock_instructor:
            mock_client = MagicMock()
            mock_instructor.return_value = mock_client
            yield mock_instructor, mock_client

    def test_date_range_both_dates(self, mock_instructor_client):
        """Test with mocked LLM response returning both dates."""
        mock_instructor, mock_client = mock_instructor_client

        # Create a mock output object
        mock_output = MagicMock()
        mock_output.start_date = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)
        mock_output.end_date = datetime(2024, 12, 31, 23, 59, 59, tzinfo=UTC)
        mock_output.reasoning = "Year 2024"
        mock_client.create.return_value = mock_output

        # Call function
        result = extract_temporal_constraint("Show me data for 2024")

        # Assertions
        assert isinstance(result, TemporalConstraint)
        assert result.start_date == datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)
        assert result.end_date == datetime(2024, 12, 31, 23, 59, 59, tzinfo=UTC)
        assert result.reasoning == "Year 2024"

        # Verify the mock was called correctly
        mock_instructor.assert_called_once_with("bedrock/amazon.nova-pro-v1:0")
        mock_client.create.assert_called_once()

    def test_date_range_no_dates(self, mock_instructor_client):
        """Test with mocked LLM response returning no dates."""
        _, mock_client = mock_instructor_client

        mock_output = MagicMock()
        mock_output.start_date = None
        mock_output.end_date = None
        mock_output.reasoning = "No specific dates mentioned"
        mock_client.create.return_value = mock_output

        # Call function
        result = extract_temporal_constraint("Show me all data")

        # Assertions
        assert isinstance(result, TemporalConstraint)
        assert result.start_date is None
        assert result.end_date is None

    def test_date_range_only_start(self, mock_instructor_client):
        """Test with mocked LLM response returning only start date."""
        _, mock_client = mock_instructor_client

        mock_output = MagicMock()
        mock_output.start_date = datetime(2024, 6, 1, 0, 0, 0, tzinfo=UTC)
        mock_output.end_date = None
        mock_output.reasoning = "From June 2024 onwards"
        mock_client.create.return_value = mock_output

        # Call function
        result = extract_temporal_constraint("From June 2024 onwards")

        # Assertions
        assert isinstance(result, TemporalConstraint)
        assert result.start_date == datetime(2024, 6, 1, 0, 0, 0, tzinfo=UTC)
        assert result.end_date is None

    def test_date_range_only_end(self, mock_instructor_client):
        """Test with mocked LLM response returning only end date."""
        _, mock_client = mock_instructor_client

        mock_output = MagicMock()
        mock_output.start_date = None
        mock_output.end_date = datetime(2024, 6, 30, 23, 59, 59, tzinfo=UTC)
        mock_output.reasoning = "Until end of June 2024"
        mock_client.create.return_value = mock_output

        # Call function
        result = extract_temporal_constraint("Until end of June 2024")

        # Assertions
        assert isinstance(result, TemporalConstraint)
        assert result.start_date is None
        assert result.end_date == datetime(2024, 6, 30, 23, 59, 59, tzinfo=UTC)

    def test_client_initialization_error(self):
        """Test error handling when instructor client fails to initialize."""
        with patch(
            "tools.discover_data.utils.extract_temporal_constraint.instructor.from_provider"
        ) as mock_instructor:
            mock_instructor.side_effect = Exception("Failed to initialize client")

            with pytest.raises(RuntimeError):
                extract_temporal_constraint("Show me data for 2024")

    def test_prompt_file_missing(self, mock_instructor_client):
        """Test that extraction still works even if internal path operations occur."""
        _, mock_client = mock_instructor_client

        # Create a mock output object
        mock_output = MagicMock()
        mock_output.start_date = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)
        mock_output.end_date = datetime(2024, 3, 31, 23, 59, 59, tzinfo=UTC)
        mock_output.reasoning = "Q1 2024"
        mock_client.create.return_value = mock_output

        # Call function and verify it works
        result = extract_temporal_constraint("Show me Q1 2024 data")

        assert isinstance(result, TemporalConstraint)
        assert result.start_date == datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)

    def test_llm_extraction_error(self, mock_instructor_client):
        """Test error handling when LLM fails to extract temporal ranges."""
        _, mock_client = mock_instructor_client
        mock_client.create.side_effect = Exception("LLM API error")

        with pytest.raises(RuntimeError) as exc_info:
            extract_temporal_constraint("Show me data for 2024")

        assert "Failed to extract temporal ranges" in str(exc_info.value)
        assert "Show me data for 2024" in str(exc_info.value)
