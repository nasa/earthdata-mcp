"""Server File - FastMCP server for CMR tools."""

import importlib.metadata
import logging
import os
import sys

import uvicorn
from dotenv import load_dotenv
from fastmcp import FastMCP
from starlette.responses import JSONResponse
from starlette.routing import Route

from loader import load_tools_from_directory
from middleware import get_cors_middleware
from prompts.instructions import MCP_SERVER_INSTRUCTIONS

load_dotenv()

# Initialize logging
logger = logging.getLogger(__name__)
log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, log_level, logging.INFO))

PACKAGE_NAME = "earthdata-mcp"

# Get server version from installed package metadata
try:
    server_version = importlib.metadata.version(PACKAGE_NAME)
except importlib.metadata.PackageNotFoundError:
    server_version = "dev"

# Initialize FastMCP server
mcp = FastMCP(
    PACKAGE_NAME,
    instructions=MCP_SERVER_INSTRUCTIONS,
    version=server_version,
)
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
app = mcp.http_app(path="/mcp/v1", middleware=[cors])

# Add health check route
app.routes.append(Route("/mcp/health", health))


def main():
    """
    Run the MCP server in the appropriate mode based on command-line arguments.

    The server can run in these modes:
    - stdio: Run as standard I/O process (useful for subprocess communication)
    - http: Run as HTTP server with Streamable HTTP transport (default)
    """

    mode = sys.argv[1] if len(sys.argv) > 1 else "http"

    if mode == "stdio":
        print("Running MCP in stdio mode...")
        mcp.run()

    elif mode in ("http", "streamable-http"):
        print("Running MCP over Streamable HTTP...")
        logger.info("Using Streamable HTTP transport (default)")
        uvicorn.run(app, host="127.0.0.1", port=5001)

    else:
        raise ValueError(f"Unknown mode: {mode}")


if __name__ == "__main__":
    main()
