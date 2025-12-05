import pytest

from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta
from pathlib import Path

from toon import decode
from mcp.server.fastmcp import FastMCP
from loader import create_simple_tool
from tools.temporal_ranges.tool import get_temporal_ranges, DateRange


@pytest.fixture(scope="module")
def mcp():
    """Create and return MCP server with tool registered."""
    mcp_instance = FastMCP("test_server")
    register = create_simple_tool(
        Path(__file__).parent.parent / "tools" / "temporal_ranges", get_temporal_ranges
    )
    register(mcp_instance)
    return mcp_instance


@pytest.fixture(scope="module")
def wrapped_func(mcp):
    """Return the wrapped tool function."""
    register = create_simple_tool(Path(__file__).parent, get_temporal_ranges)
    return register(mcp)


# ===== Direct function tests (no MCP) =====


def test_direct_function_with_dates():
    """Test the function directly with both dates."""
    result = get_temporal_ranges("Show me data from November 20 to November 25, 2025")
    assert result[0]["StartDate"].strftime("%Y-%m-%dT%H:%M:%S") == "2025-11-20T00:00:00"
    assert result[0]["EndDate"].strftime("%Y-%m-%dT%H:%M:%S") == "2025-11-25T23:59:59"


def test_direct_function_no_dates():
    """Test with no dates provided."""
    result = get_temporal_ranges("Show me all available data")
    assert result[0]["StartDate"] is None
    assert result[0]["EndDate"] is None


def test_direct_function_only_start():
    """Test with only start date."""
    result = get_temporal_ranges("Show me data from November 20, 2025 onwards")
    assert result[0]["StartDate"].strftime("%Y-%m-%dT%H:%M:%S") == "2025-11-20T00:00:00"
    assert result[0]["EndDate"] is None


def test_direct_function_only_end():
    """Test with only end date."""
    result = get_temporal_ranges("Show me data until November 25, 2025")
    assert result[0]["StartDate"] is None
    assert result[0]["EndDate"].strftime("%Y-%m-%dT%H:%M:%S") == "2025-11-25T23:59:59"


# ===== MCP wrapper tests =====


@pytest.mark.asyncio
async def test_via_mcp_wrapper(wrapped_func):
    """Test via the MCP wrapper."""
    result = await wrapped_func(
        query="Show me data from November 20 to November 25, 2025"
    )

    decoded = decode(result[0])
    assert decoded[0]["StartDate"].startswith("2025-11-20T00:00:00")
    assert decoded[0]["EndDate"].startswith("2025-11-25T23:59:59")


@pytest.mark.asyncio
async def test_via_call_tool(mcp):
    """Test via MCP call_tool interface."""
    result = await mcp.call_tool(
        "get_temporal_ranges",
        {"query": "Show me data from November 20 to November 25, 2025"},
    )

    content_text = result[0].text if hasattr(result[0], "text") else str(result[0])
    decoded = decode(content_text)
    assert decoded[0]["StartDate"].startswith("2025-11-20T00:00:00")
    assert decoded[0]["EndDate"].startswith("2025-11-25T23:59:59")


@pytest.mark.asyncio
async def test_via_call_tool_no_dates(mcp):
    """Test via MCP with no dates."""
    result = await mcp.call_tool(
        "get_temporal_ranges", {"query": "Show me all available data"}
    )

    content_text = result[0].text if hasattr(result[0], "text") else str(result[0])
    decoded = decode(content_text)
    assert decoded[0]["StartDate"] is None
    assert decoded[0]["EndDate"] is None


@pytest.mark.asyncio
async def test_tool_is_registered(mcp):
    """Verify tool is registered with MCP."""
    tools = await mcp.list_tools()
    tool_names = [tool.name for tool in tools]
    assert "get_temporal_ranges" in tool_names


def test_spring_four_years_ago():
    """Test relative date: spring of four years ago."""
    now = datetime.now(timezone.utc)
    four_years_ago = now.year - 4
    expected_start = datetime(four_years_ago, 3, 1, 0, 0, 0, tzinfo=timezone.utc)
    expected_end = datetime(four_years_ago, 5, 31, 23, 59, 59, tzinfo=timezone.utc)

    result = get_temporal_ranges("spring of four years ago")

    # Allow some timezone flexibility in comparison
    assert (
        result[0]["StartDate"].replace(tzinfo=timezone.utc).date()
        == expected_start.date()
    )
    assert (
        result[0]["EndDate"].replace(tzinfo=timezone.utc).date() == expected_end.date()
    )


def test_spring_argentina():
    """Test relative date with location: this winter in Argentina (southern hemisphere)"""
    now = datetime.now(timezone.utc)
    current_year = now.year
    # Winter in Argentina (southern hemisphere) is June-August
    expected_start = datetime(current_year, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
    expected_end = datetime(current_year, 8, 31, 23, 59, 59, tzinfo=timezone.utc)

    result = get_temporal_ranges("this winter in argentina")

    assert (
        result[0]["StartDate"].replace(tzinfo=timezone.utc).date()
        == expected_start.date()
    )
    assert (
        result[0]["EndDate"].replace(tzinfo=timezone.utc).date() == expected_end.date()
    )


def test_last_month():
    """Test relative date: last month."""
    now = datetime.now(timezone.utc)
    last_month_date = now - relativedelta(months=1)

    # Get first day of last month
    expected_start = datetime(
        last_month_date.year, last_month_date.month, 1, 0, 0, 0, tzinfo=timezone.utc
    )

    # Get last day of last month
    # Move to first day of current month, then subtract one day
    first_of_current = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    last_of_last_month = first_of_current - relativedelta(days=1)
    expected_end = datetime(
        last_of_last_month.year,
        last_of_last_month.month,
        last_of_last_month.day,
        23,
        59,
        59,
        tzinfo=timezone.utc,
    )

    result = get_temporal_ranges("last month")

    assert (
        result[0]["StartDate"].replace(tzinfo=timezone.utc).date()
        == expected_start.date()
    )
    assert (
        result[0]["EndDate"].replace(tzinfo=timezone.utc).date() == expected_end.date()
    )


def test_atlantic_hurricane_season():
    """Test seasonal pattern: Atlantic hurricane season."""
    now = datetime.now(timezone.utc)
    current_year = now.year
    # Atlantic hurricane season: June 1 - November 30
    expected_start = datetime(current_year, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
    expected_end = datetime(current_year, 11, 30, 23, 59, 59, tzinfo=timezone.utc)

    result = get_temporal_ranges("Atlantic hurricane season")

    assert (
        result[0]["StartDate"].replace(tzinfo=timezone.utc).date()
        == expected_start.date()
    )
    assert (
        result[0]["EndDate"].replace(tzinfo=timezone.utc).date() == expected_end.date()
    )


def test_indian_monsoon_season():
    """Test seasonal pattern: Indian monsoon season."""
    now = datetime.now(timezone.utc)
    current_year = now.year
    # Indian monsoon season: June 1 - September 30
    expected_start = datetime(current_year, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
    expected_end = datetime(current_year, 9, 30, 23, 59, 59, tzinfo=timezone.utc)

    result = get_temporal_ranges("Indian monsoon season")

    assert (
        result[0]["StartDate"].replace(tzinfo=timezone.utc).date()
        == expected_start.date()
    )
    assert (
        result[0]["EndDate"].replace(tzinfo=timezone.utc).date() == expected_end.date()
    )
