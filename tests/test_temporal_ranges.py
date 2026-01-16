"""Unit tests for temporal ranges tool with mocked LLM responses."""

import sys
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from tools.temporal_ranges.input_model import TemporalRangeInput
from tools.temporal_ranges.output_model import TemporalRangeOutput
from tools.temporal_ranges.tool import get_temporal_ranges


class TestTemporalRangesMocked:
    """Mocked unit tests for temporal ranges (no LLM dependency)."""

    @pytest.fixture
    def mock_instructor_client(self):
        """Fixture to create a mocked instructor client."""
        with patch("tools.temporal_ranges.tool.instructor.from_provider") as mock_instructor:
            mock_client = MagicMock()
            mock_instructor.return_value = mock_client
            yield mock_instructor, mock_client

    def test_date_range_both_dates(self, mock_instructor_client):
        """Test with mocked LLM response returning both dates."""
        mock_instructor, mock_client = mock_instructor_client

        mock_date_range = TemporalRangeOutput(
            StartDate=datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC),
            EndDate=datetime(2024, 12, 31, 23, 59, 59, tzinfo=UTC),
            reasoning="Year 2024",
        )
        mock_client.create.return_value = mock_date_range

        # Call function
        result = get_temporal_ranges(TemporalRangeInput(timerange_string="Show me data for 2024"))

        # Assertions
        assert result["StartDate"] == datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)
        assert result["EndDate"] == datetime(2024, 12, 31, 23, 59, 59, tzinfo=UTC)

        # Verify the mock was called correctly
        mock_instructor.assert_called_once_with("bedrock/amazon.nova-pro-v1:0")
        mock_client.create.assert_called_once()

    def test_date_range_no_dates(self, mock_instructor_client):
        """Test with mocked LLM response returning no dates."""
        _, mock_client = mock_instructor_client

        mock_date_range = TemporalRangeOutput(
            StartDate=None, EndDate=None, reasoning="No specific dates mentioned"
        )
        mock_client.create.return_value = mock_date_range

        # Call function
        result = get_temporal_ranges(TemporalRangeInput(timerange_string="Show me all data"))

        # Assertions
        assert result["StartDate"] is None
        assert result["EndDate"] is None

    def test_date_range_only_start(self, mock_instructor_client):
        """Test with mocked LLM response returning only start date."""
        _, mock_client = mock_instructor_client

        mock_date_range = TemporalRangeOutput(
            StartDate=datetime(2024, 6, 1, 0, 0, 0, tzinfo=UTC),
            EndDate=None,
            reasoning="From June 2024 onwards",
        )
        mock_client.create.return_value = mock_date_range

        # Call function
        result = get_temporal_ranges(TemporalRangeInput(timerange_string="From June 2024 onwards"))

        # Assertions
        assert result["StartDate"] == datetime(2024, 6, 1, 0, 0, 0, tzinfo=UTC)
        assert result["EndDate"] is None

    def test_date_range_only_end(self, mock_instructor_client):
        """Test with mocked LLM response returning only end date."""
        _, mock_client = mock_instructor_client

        mock_date_range = TemporalRangeOutput(
            StartDate=None,
            EndDate=datetime(2024, 6, 30, 23, 59, 59, tzinfo=UTC),
            reasoning="Until end of June 2024",
        )
        mock_client.create.return_value = mock_date_range

        # Call function
        result = get_temporal_ranges(TemporalRangeInput(timerange_string="Until end of June 2024"))

        # Assertions
        assert result["StartDate"] is None
        assert result["EndDate"] == datetime(2024, 6, 30, 23, 59, 59, tzinfo=UTC)

    def test_client_initialization_error(self):
        """Test error handling when instructor client fails to initialize."""
        with patch("tools.temporal_ranges.tool.instructor.from_provider") as mock_instructor:
            mock_instructor.side_effect = Exception("Failed to initialize client")

            with pytest.raises(RuntimeError) as exc_info:
                get_temporal_ranges(TemporalRangeInput(timerange_string="Show me data for 2024"))

            assert "Failed to initialize instructor client" in str(exc_info.value)
            assert "bedrock" in str(exc_info.value)
            assert "amazon.nova-pro-v1:0" in str(exc_info.value)

    def test_prompt_file_missing(self, mock_instructor_client):
        """Test error handling when prompt.md file is missing."""
        _, _ = mock_instructor_client

        # Mock Path to point to a non-existent location
        with patch("tools.temporal_ranges.tool.Path") as mock_path:
            mock_prompt_path = MagicMock()
            mock_prompt_path.exists.return_value = False
            mock_path.return_value.parent = MagicMock()
            mock_path.return_value.parent.__truediv__ = lambda self, other: mock_prompt_path

            with pytest.raises(FileNotFoundError) as exc_info:
                get_temporal_ranges(TemporalRangeInput(timerange_string="Show me data for 2024"))

            assert "Required prompt file not found" in str(exc_info.value)

    def test_llm_extraction_error(self, mock_instructor_client):
        """Test error handling when LLM fails to extract temporal ranges."""
        _, mock_client = mock_instructor_client
        mock_client.create.side_effect = Exception("LLM API error")

        with pytest.raises(RuntimeError) as exc_info:
            get_temporal_ranges(TemporalRangeInput(timerange_string="Show me data for 2024"))

        assert "Failed to extract temporal ranges" in str(exc_info.value)
        assert "Show me data for 2024" in str(exc_info.value)

    def test_langfuse_none_during_error(self, mock_instructor_client):
        """Test that errors are handled gracefully when LANGFUSE is None."""
        # This tests the conditional `if LANGFUSE:` checks in the error handlers
        mock_instructor, mock_client = mock_instructor_client

        # Temporarily set LANGFUSE to None to simulate failed initialization
        import tools.temporal_ranges.tool as tool_module  # pylint: disable=import-outside-toplevel

        original_langfuse = tool_module.LANGFUSE
        tool_module.LANGFUSE = None

        try:
            # Test client initialization error with langfuse=None
            mock_instructor.side_effect = Exception("Client init failed")

            with pytest.raises(RuntimeError) as exc_info:
                get_temporal_ranges(TemporalRangeInput(timerange_string="Show me data for 2024"))

            assert "Failed to initialize instructor client" in str(exc_info.value)

            # Reset for next test
            mock_instructor.side_effect = None
            mock_instructor.return_value = mock_client

            # Test LLM error with langfuse=None
            mock_client.create.side_effect = Exception("LLM failed")

            with pytest.raises(RuntimeError) as exc_info:
                get_temporal_ranges(TemporalRangeInput(timerange_string="Show me data for 2024"))

            assert "Failed to extract temporal ranges" in str(exc_info.value)

        finally:
            # Restore original LANGFUSE
            tool_module.LANGFUSE = original_langfuse

    def test_langfuse_initialization_exception(self):
        """Test the exception handler when Langfuse client fails to initialize at import time."""
        # Save original module state
        original_module = sys.modules.get("tools.temporal_ranges.tool")

        # Remove the module and its dependencies from sys.modules
        modules_to_remove = [k for k in sys.modules if "tools.temporal_ranges.tool" in k]
        for module in modules_to_remove:
            sys.modules.pop(module, None)

        try:
            # Mock get_client to raise an exception at import time
            with patch("langfuse.get_client", side_effect=Exception("Langfuse init failed")):
                # Reimport the module - should catch the exception and set LANGFUSE=None
                import tools.temporal_ranges.tool as reimported_module  # pylint: disable=import-outside-toplevel

                # Verify LANGFUSE was set to None after the exception
                assert reimported_module.LANGFUSE is None
        finally:
            # Restore original module state
            if original_module:
                sys.modules["tools.temporal_ranges.tool"] = original_module
            else:
                sys.modules.pop("tools.temporal_ranges.tool", None)
