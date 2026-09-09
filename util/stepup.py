"""HTTP-layer step-up: turn a failed per-tool check into an HTTP 401/403 challenge.

This runs BEFORE the MCP transport sees the request, which is the only place an
HTTP status can be chosen. An MCP client that receives 401 + WWW-Authenticate
starts its OAuth flow and then retries the same tools/call.

ASGI stack, outermost first:
  AuthenticationMiddleware(BearerAuthBackend)  parses Authorization -> scope["user"]   (never rejects)
  AuthContextMiddleware                        exposes the token to tool code           (never rejects)
  StepUpAuth (this file)                       per-tool challenge for protected tools
  streamable-HTTP MCP endpoint
"""

import json
import logging

from fastmcp.server.auth import AuthContext
from fastmcp.server.auth.middleware import RequireAuthMiddleware
from fastmcp.server.auth import require_scopes
from mcp.server.auth.middleware.bearer_auth import AuthenticatedUser

logger = logging.getLogger(__name__)


class StepUpAuth:
    def __init__(self, app, *, tool_manifests, resource_metadata_url):
        self.app = app
        self.tool_manifests = tool_manifests  # tool name -> AuthCheck (must expose .scopes and .label)
        self.resource_metadata_url = resource_metadata_url

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] != "POST":
            return await self.app(scope, receive, send)

        body, receive = await _buffer_body(receive)
        name = _called_tool(body)
        logger.info(f"StepUpAuth: called tool '{name}'")
        logger.info(f"StepUpAuth: self.tool_manifests = {self.tool_manifests}")
        tool_auth = self.tool_manifests.get(name, False)
        logger.info(f"StepUpAuth: tool_auth = {tool_auth}")
        if tool_auth is False:
            logger.info(f"StepUpAuth: tool '{name}' does not require auth")
            return await self.app(scope, receive, send)

        user = scope.get("user")
        token = user.access_token if isinstance(user, AuthenticatedUser) else None
        if token is not None:
            return await self.app(scope, receive, send)

        status = "401 (no valid token)" if token is None else "403 insufficient_scope"

        logger.info(f"StepUpAuth: HTTP {status} challenge for tool '{name}'")
        # Reuse the framework's own enforcement for the response. It picks 401 vs 403 and
        # builds the WWW-Authenticate header (resource_metadata=..., scope=...).
        gate = RequireAuthMiddleware(
            self.app,
            required_scopes=[],
            resource_metadata_url=self.resource_metadata_url,
        )
        await gate(scope, receive, send)


async def _buffer_body(receive):
    """Read the whole request body, then hand back a receive() that replays it."""
    chunks, more = [], True
    while more:
        message = await receive()
        chunks.append(message.get("body", b""))
        more = message.get("more_body", False)
    body = b"".join(chunks)
    replayed = False

    async def replay():
        nonlocal replayed
        if replayed:
            return await receive()
        replayed = True
        return {"type": "http.request", "body": body, "more_body": False}

    return body, replay


def _called_tool(body: bytes) -> str | None:
    """Tool name if the JSON-RPC body is a tools/call, else None."""
    try:
        parsed = json.loads(body)
    except ValueError:
        return None
    for msg in parsed if isinstance(parsed, list) else [parsed]:
        if isinstance(msg, dict) and msg.get("method") == "tools/call":
            return (msg.get("params") or {}).get("name")
    return None
