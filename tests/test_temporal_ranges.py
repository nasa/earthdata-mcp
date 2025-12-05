import pytest
from datetime import datetime
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
    result = get_temporal_ranges(
        DateRange(start=datetime(2025, 11, 20), end=datetime(2025, 11, 25))
    )
    assert result[0]["StartDate"] == datetime(2025, 11, 20)
    assert result[0]["EndDate"] == datetime(2025, 11, 25)


def test_direct_function_no_dates():
    """Test with no dates provided."""
    result = get_temporal_ranges(DateRange())
    assert result[0]["StartDate"] is None
    assert result[0]["EndDate"] is None


def test_direct_function_only_start():
    """Test with only start date."""
    result = get_temporal_ranges(DateRange(start=datetime(2025, 11, 20)))
    assert result[0]["StartDate"] == datetime(2025, 11, 20)
    assert result[0]["EndDate"] is None


def test_direct_function_only_end():
    """Test with only end date."""
    result = get_temporal_ranges(DateRange(end=datetime(2025, 11, 25)))
    assert result[0]["StartDate"] is None
    assert result[0]["EndDate"] == datetime(2025, 11, 25)


# ===== MCP wrapper tests =====


@pytest.mark.asyncio
async def test_via_mcp_wrapper(wrapped_func):
    """Test via the MCP wrapper."""
    result = await wrapped_func(
        daterange=DateRange(start=datetime(2025, 11, 20), end=datetime(2025, 11, 25))
    )

    decoded = decode(result[0])
    assert decoded[0]["StartDate"] == "2025-11-20T00:00:00"
    assert decoded[0]["EndDate"] == "2025-11-25T00:00:00"


@pytest.mark.asyncio
async def test_via_call_tool(mcp):
    """Test via MCP call_tool interface."""
    result = await mcp.call_tool(
        "get_temporal_ranges",
        {"daterange": {"start": "2025-11-20T00:00:00", "end": "2025-11-25T00:00:00"}},
    )

    content_text = result[0].text if hasattr(result[0], "text") else str(result[0])
    decoded = decode(content_text)
    assert decoded[0]["StartDate"] == "2025-11-20T00:00:00"
    assert decoded[0]["EndDate"] == "2025-11-25T00:00:00"


@pytest.mark.asyncio
async def test_via_call_tool_no_dates(mcp):
    """Test via MCP with no dates."""
    result = await mcp.call_tool("get_temporal_ranges", {"daterange": {}})

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
