"""Server File - FastMCP server for CMR tools."""

import importlib.metadata
import logging
import os
import sys

import uvicorn
from dotenv import load_dotenv
from fastmcp import FastMCP
from fastmcp.server.auth import OAuthProxy
from fastmcp.server.auth.providers.jwt import JWTVerifier
from starlette.middleware import Middleware as ASGIMiddleware
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route
from mcp.server.auth.routes import build_resource_metadata_url

from pydantic import AnyHttpUrl
from loader import load_tools_from_directory
from middleware import get_cors_middleware
from prompts.instructions import MCP_SERVER_INSTRUCTIONS
from util.stepup import StepUpAuth

load_dotenv()

# Initialize logging
logger = logging.getLogger(__name__)
log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

PACKAGE_NAME = "earthdata-mcp"

URS_HOST = os.environ.get("URS_HOST", "https://sit.urs.earthdata.nasa.gov")
URS_CLIENT_ID = os.environ.get("URS_CLIENT_ID")
URS_CLIENT_SECRET = os.environ.get("URS_CLIENT_SECRET")
MCP_HOST = os.environ.get("MCP_HOST", "http://localhost:5001")
MCP_PATH = "/mcp/v1"

# Get server version from installed package metadata
try:
    server_version = importlib.metadata.version(PACKAGE_NAME)
except importlib.metadata.PackageNotFoundError:
    server_version = "dev"

# Configure token verification for your provider
# See the Token Verification guide for provider-specific setups
token_verifier = JWTVerifier(
    jwks_uri=URS_HOST + "/.well-known/edl_sit_jwks.json",
    issuer=URS_HOST,
)

# Create the OAuth proxy
auth = OAuthProxy(
    # Provider's OAuth endpoints (from their documentation)
    upstream_authorization_endpoint=URS_HOST + "/oauth/authorize",
    upstream_token_endpoint=URS_HOST + "/oauth/token",

    # Your registered app credentials
    upstream_client_id=URS_CLIENT_ID,
    upstream_client_secret=URS_CLIENT_SECRET,

    # Token validation (see Token Verification guide)
    token_verifier=token_verifier,

    # Your FastMCP server's public URL
    base_url=MCP_HOST + "/mcp/v1",
    # base_url=MCP_HOST,
    issuer_url=MCP_HOST,

    resource_base_url=MCP_HOST,
    # redirect_path="/mcp/v1/auth/callback",

    # EDL handles the consent
    require_authorization_consent="external",
    # Do not forward the resource to the upstream provider
    forward_resource=False,
)

# Initialize FastMCP server
mcp = FastMCP(
    PACKAGE_NAME,
    instructions=MCP_SERVER_INSTRUCTIONS,
    version=server_version,
)
cors = get_cors_middleware()

try:
    # Load tool plugins
    result = load_tools_from_directory(mcp)
    manifests = result.get("manifests", [])
    logger.info("Successfully loaded tools from directory")
except Exception as e:
    logger.error("Failed to load tools: %s", e)
    raise


# Health check endpoint for ALB (matches CMR health format)
async def health(_request):
    """Health check endpoint for load balancer."""
    return JSONResponse({"earthdata-mcp": {"ok?": True}})

middleware = list(auth.get_middleware())

metadata_url = build_resource_metadata_url(AnyHttpUrl(f"{MCP_HOST}{MCP_PATH}"))

middleware.append(ASGIMiddleware(StepUpAuth, tool_manifests=manifests, resource_metadata_url=metadata_url))
middleware.append(cors)

# Build the app with middleware and the intended path
app = mcp.http_app(path=MCP_PATH, middleware=middleware)
# app = mcp.http_app(path="/", middleware=middleware)

auth_routes = auth.get_routes(mcp_path=MCP_PATH)
# auth_routes = auth.get_routes()

print(auth_routes)

well_known = [route for route in auth_routes if route.path.startswith("/.well-known")]
operational = [route for route in auth_routes if not route.path.startswith("/.well-known")]

app.routes.extend(auth_routes)
app.routes.extend(well_known)
as_metadata = next(route for route in well_known if route.path == "/.well-known/oauth-authorization-server")
app.routes.append(Route("/.well-known/oauth-authorization-server/mcp", as_metadata.endpoint, methods=["GET", "OPTIONS"]))

# register_metadata = next(route for route in operational if route.path == "/register")
# app.routes.append(Route("/mcp/v1/register", register_metadata.endpoint, methods=["GET", "OPTIONS"]))

app.routes.append(Mount("/mcp/v1", routes=operational))

# Add health check route
app.routes.append(Route("/mcp/health", health))

all_routes = app.routes
print(all_routes)


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
