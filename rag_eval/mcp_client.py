"""Client for interacting with the Earthdata MCP server."""

import json
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class EarthdataRAGClient:
    """Client for querying the Earthdata MCP server's discover_data tool"""

    def __init__(self, server_url: str):
        self.server_url = server_url
        self.client = httpx.Client(timeout=60.0)
        self.session_id: Optional[str] = None
        self._initialize_session()

    def _initialize_session(self):
        """Initialize MCP session and get session ID from server"""
        try:
            init_request = {
                "jsonrpc": "2.0",
                "id": 0,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "earthdata-rag-eval",
                        "version": "1.0.0",
                    },
                },
            }
            logger.info("Initializing MCP session...")

            response = self.client.post(
                self.server_url,
                json=init_request,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                },
            )

            logger.debug(f"Initialize response status: {response.status_code}")
            logger.debug(f"Response headers: {dict(response.headers)}")
            logger.debug(f"Response text: {response.text[:500]}")

            response.raise_for_status()

            # Try to get session ID from response header first
            self.session_id = response.headers.get("mcp-session-id")
            if self.session_id:
                logger.info(f"Got session ID from header: {self.session_id}")
                return

            # Otherwise parse from SSE response body
            for line in response.text.split("\n"):
                if line.startswith("data: "):
                    data = line[6:].strip()
                    if data and data != "[DONE]":
                        try:
                            result = json.loads(data)
                            logger.debug(
                                f"Initialize result: {json.dumps(result, indent=2)}"
                            )
                            break
                        except json.JSONDecodeError as e:
                            logger.warning(f"JSON decode error: {e}")
                            continue

            if not self.session_id:
                logger.warning("No session ID received from server")

            # List available tools after initialization
            self._list_tools()

        except Exception as e:
            logger.error(f"Error initializing session: {e}", exc_info=True)

    def _list_tools(self):
        """List available tools from the MCP server"""
        try:
            list_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/list",
                "params": {},
            }

            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            }
            if self.session_id:
                headers["mcp-session-id"] = self.session_id

            logger.info("Listing available tools...")
            response = self.client.post(
                self.server_url,
                json=list_request,
                headers=headers,
            )

            logger.debug(f"List tools response status: {response.status_code}")
            logger.debug(f"Response text: {response.text}")

            # Parse SSE response
            for line in response.text.split("\n"):
                if line.startswith("data: "):
                    data = line[6:].strip()
                    if data and data != "[DONE]":
                        try:
                            result = json.loads(data)
                            if "result" in result and "tools" in result["result"]:
                                tools = result["result"]["tools"]
                                logger.info(f"Available tools ({len(tools)}):")
                                for tool in tools:
                                    logger.info(
                                        f"  - {tool.get('name')}: {tool.get('description', '')[:80]}"
                                    )
                            break
                        except json.JSONDecodeError:
                            continue

        except Exception as e:
            logger.error(f"Error listing tools: {e}")

    def query(self, question: str, max_results: int = 5) -> dict:
        """
        Query the Earthdata MCP server using the discover_data tool.

        Args:
            question: Natural language query
            max_results: Maximum number of results to return

        Returns:
            dict with 'answer' and 'logs' keys
        """
        try:
            # Build request - tool expects a single 'params' parameter containing DiscoverDataInput
            request_json = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "discover_data",
                    "arguments": {
                        "params": {"query": question, "max_results": max_results}
                    },
                },
            }

            # Prepare headers
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            }

            # Add session ID to header if we have one
            if self.session_id:
                headers["mcp-session-id"] = self.session_id
                logger.debug(f"Using session ID: {self.session_id}")
            else:
                logger.warning("No session ID available!")

            logger.debug(f"Request: {json.dumps(request_json, indent=2)}")
            logger.debug(f"Headers: {headers}")

            # Call the MCP server's discover_data tool
            response = self.client.post(
                self.server_url,
                json=request_json,
                headers=headers,
            )

            logger.debug(f"Response status: {response.status_code}")
            logger.debug(f"Response headers: {dict(response.headers)}")
            logger.debug(f"Response text: {response.text}")

            response.raise_for_status()

            # Parse SSE response
            result_data = None
            for line in response.text.split("\n"):
                if line.startswith("data: "):
                    data = line[6:].strip()  # Remove 'data: ' prefix
                    if data and data != "[DONE]":
                        try:
                            result_data = json.loads(data)
                        except json.JSONDecodeError:
                            continue

            if not result_data:
                return {
                    "answer": "No results found",
                    "logs": "Empty response from server",
                }

            # Extract the tool result from MCP response
            if "result" in result_data and "content" in result_data["result"]:
                content = result_data["result"]["content"]
                if isinstance(content, list) and len(content) > 0:
                    text_content = content[0].get("text", "")
                    if text_content:
                        try:
                            # If text_content is already a dict, use it directly
                            if isinstance(text_content, dict):
                                discover_result = text_content
                            else:
                                # Otherwise parse as JSON (possibly double-encoded)
                                discover_result = json.loads(text_content)
                                # Check if it's double-encoded
                                if isinstance(discover_result, str):
                                    discover_result = json.loads(discover_result)

                            # Format as answer string
                            answer = self._format_answer(discover_result)

                            return {
                                "answer": answer,
                                "logs": f"Found {len(discover_result.get('collections', []))} collections",
                                "raw_result": discover_result,
                            }
                        except (json.JSONDecodeError, AttributeError, TypeError) as e:
                            # If it's not JSON or can't be parsed, return as-is
                            logger.debug(f"Response is not JSON, treating as text: {e}")
                            return {
                                "answer": str(text_content),
                                "logs": "Received text response",
                            }

            return {"answer": "No results found", "logs": "Empty response from server"}

        except Exception as e:
            logger.error(f"Error querying MCP server: {e}", exc_info=True)
            return {
                "answer": f"Error querying MCP server: {str(e)}",
                "logs": f"Exception: {type(e).__name__}",
            }

    def _format_answer(self, discover_result: dict) -> str:
        """Format discover_data result as a readable answer"""
        collections = discover_result.get("collections", [])

        if not collections:
            return "No matching datasets found."

        answer_parts = [f"Found {len(collections)} relevant dataset(s):\n"]

        for i, collection in enumerate(collections[:5], 1):
            concept_id = collection.get("concept_id", "Unknown")
            title = collection.get("title", "Unknown")
            abstract = collection.get("abstract", "No description available")
            score = collection.get("similarity_score", 0.0)

            # Truncate abstract for readability
            if len(abstract) > 300:
                abstract = abstract[:300] + "..."

            answer_parts.append(
                f"{i}. {title}\n"
                f"   ID: {concept_id}\n"
                f"   Relevance: {score:.3f}\n"
                f"   {abstract}\n"
            )

        return "\n".join(answer_parts)

    def close(self):
        """Close the HTTP client"""
        if hasattr(self, "client") and self.client is not None:
            self.client.close()

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
        return False
