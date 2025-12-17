"""Middleware modules for FastMCP server."""

from .cors import get_cors_middleware

__all__ = ["get_cors_middleware"]
