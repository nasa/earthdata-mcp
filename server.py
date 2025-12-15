import sys
import logging
import uvicorn
from dotenv import load_dotenv
from fastmcp import FastMCP
from loader import load_tools_from_directory
from middleware import get_cors_middleware

load_dotenv()

# Initialize logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

# Initialize FastMCP server
mcp = FastMCP("cmr-mcps")

# Get CORS middleware configuration
cors = get_cors_middleware()

try:
    # Load tool plugins
    load_tools_from_directory(mcp)
    logger.info("Successfully loaded tools from directory")
except Exception as e:
    logger.error(f"Failed to load tools: {e}")
    raise e

# Build the app with middleware and the intended path
app = mcp.http_app(path="/mcp", middleware=[cors])


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "http"

    if mode == "stdio":
        print("Running MCP in stdio mode...")
        mcp.run()

    elif (mode == "http") or (mode == "sse"):
        print("Running MCP over HTTP streaming...")
        uvicorn.run(app, host="127.0.0.1", port=5001)

    else:
        raise ValueError(f"Unknown mode: {mode}")


if __name__ == "__main__":
    main()
