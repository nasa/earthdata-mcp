"""Server File - FastMCP server for CMR tools."""

import logging
import sys

import uvicorn
from dotenv import load_dotenv
from fastmcp import FastMCP
from starlette.responses import JSONResponse
from starlette.routing import Route

from loader import load_tools_from_directory
from middleware import get_cors_middleware

load_dotenv()

# Initialize logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

# Initialize FastMCP server
mcp = FastMCP("earthdata-mcp")

# Get CORS middleware configuration
cors = get_cors_middleware()

try:
    # Load tool plugins
    load_tools_from_directory(mcp)
    logger.info("Successfully loaded tools from directory")
except Exception as e:
    logger.error("Failed to load tools: %s", e)
    raise


# Health check endpoint for ALB (matches CMR health format)
async def health(_request):
    """Health check endpoint for load balancer."""
    return JSONResponse({"earthdata-mcp": {"ok?": True}})


# Build the app with middleware and the intended path
app = mcp.http_app(path="/mcp", middleware=[cors])

# Add health check route
app.routes.append(Route("/mcp/health", health))


def main():
    """
    Run the MCP server in the appropriate mode based on command-line arguments.

    The server can run in these modes:
    - stdio: Run as standard I/O process (useful for subprocess communication)
    - http/sse: Run as HTTP server with streaming responses (default)
    """

    mode = sys.argv[1] if len(sys.argv) > 1 else "http"

    if mode == "stdio":
        print("Running MCP in stdio mode...")
        mcp.run()

    elif mode in ("http", "sse"):
        print("Running MCP over HTTP streaming...")
        uvicorn.run(app, host="127.0.0.1", port=5001)

    else:
        raise ValueError(f"Unknown mode: {mode}")


if __name__ == "__main__":
    main()
