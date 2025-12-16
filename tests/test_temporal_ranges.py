from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
from tools.temporal_ranges.tool import get_temporal_ranges, DateRange
from tools.temporal_ranges.input_model import TemporalRangeInput


# ===== Mocked unit tests (no LLM dependency) =====


@patch("tools.temporal_ranges.tool.instructor.from_provider")
def test_mocked_date_range_both_dates(mock_instructor):
    """Test with mocked LLM response returning both dates."""
    # Setup mock
    mock_client = MagicMock()
    mock_instructor.return_value = mock_client

    mock_date_range = DateRange(
        start_date=datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
        end_date=datetime(2024, 12, 31, 23, 59, 59, tzinfo=timezone.utc),
        reasoning="Year 2024",
    )
    mock_client.create.return_value = mock_date_range

    # Call function
    result = get_temporal_ranges(
        TemporalRangeInput(timerange_string="Show me data for 2024")
    )

    # Assertions
    assert result["StartDate"] == datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    assert result["EndDate"] == datetime(2024, 12, 31, 23, 59, 59, tzinfo=timezone.utc)

    # Verify the mock was called correctly
    mock_instructor.assert_called_once_with("bedrock/amazon.nova-pro-v1:0")
    mock_client.create.assert_called_once()


@patch("tools.temporal_ranges.tool.instructor.from_provider")
def test_mocked_date_range_no_dates(mock_instructor):
    """Test with mocked LLM response returning no dates."""
    # Setup mock
    mock_client = MagicMock()
    mock_instructor.return_value = mock_client

    mock_date_range = DateRange(
        start_date=None, end_date=None, reasoning="No specific dates mentioned"
    )
    mock_client.create.return_value = mock_date_range

    # Call function
    result = get_temporal_ranges(
        TemporalRangeInput(timerange_string="Show me all data")
    )

    # Assertions
    assert result["StartDate"] is None
    assert result["EndDate"] is None


@patch("tools.temporal_ranges.tool.instructor.from_provider")
def test_mocked_date_range_only_start(mock_instructor):
    """Test with mocked LLM response returning only start date."""
    # Setup mock
    mock_client = MagicMock()
    mock_instructor.return_value = mock_client

    mock_date_range = DateRange(
        start_date=datetime(2024, 6, 1, 0, 0, 0, tzinfo=timezone.utc),
        end_date=None,
        reasoning="From June 2024 onwards",
    )
    mock_client.create.return_value = mock_date_range

    # Call function
    result = get_temporal_ranges(
        TemporalRangeInput(timerange_string="From June 2024 onwards")
    )

    # Assertions
    assert result["StartDate"] == datetime(2024, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
    assert result["EndDate"] is None


@patch("tools.temporal_ranges.tool.instructor.from_provider")
def test_mocked_date_range_only_end(mock_instructor):
    """Test with mocked LLM response returning only end date."""
    # Setup mock
    mock_client = MagicMock()
    mock_instructor.return_value = mock_client

    mock_date_range = DateRange(
        start_date=None,
        end_date=datetime(2024, 6, 30, 23, 59, 59, tzinfo=timezone.utc),
        reasoning="Until end of June 2024",
    )
    mock_client.create.return_value = mock_date_range

    # Call function
    result = get_temporal_ranges(
        TemporalRangeInput(timerange_string="Until end of June 2024")
    )

    # Assertions
    assert result["StartDate"] is None
    assert result["EndDate"] == datetime(2024, 6, 30, 23, 59, 59, tzinfo=timezone.utc)
