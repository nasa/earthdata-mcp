"""CORS middleware configuration for FastMCP server."""

from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware


def get_cors_middleware() -> Middleware:
    """
    Create and return CORS middleware configuration.

    Returns:
        Middleware: Configured CORS middleware for FastMCP server
    """
    return Middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:6274",  # MCP Inspector
        ],
        allow_methods=["POST", "OPTIONS", "GET"],
        allow_headers=["*"],
        expose_headers=["Mcp-Session-Id"],
        allow_credentials=True,
    )
