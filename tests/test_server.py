import pytest
from pathlib import Path
from mcp.server.fastmcp import FastMCP
from loader import create_simple_tool
from tools.temporal_ranges.tool import get_temporal_ranges

# ===== Integration test MCP loading =====


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
