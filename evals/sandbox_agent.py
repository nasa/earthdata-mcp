"""Synchronous Bedrock + MCP agentic loop for regression tests.

lru_cache on _bedrock_agent_task is the task→evaluator handoff: the task primes
the cache, evaluators call the same function and get back the same result without
triggering a second Bedrock invocation.
"""

import json
import os
import time
from dataclasses import dataclass, field
from functools import cache
from typing import Any

import boto3
import httpx
from dotenv import load_dotenv
from langfuse import get_client, observe
from mcp.types import CallToolResult, TextContent

load_dotenv()

DEFAULT_BEDROCK_MAX_TURNS = 5


@dataclass
class _ToolInvocation:
    name: str
    args: dict[str, Any]
    output: list[dict[str, Any]]
    mcp_result: CallToolResult
    start_time: float
    end_time: float
    is_error: bool


@dataclass
class _AgentResult:
    final_output: Any
    invocations: list[_ToolInvocation] = field(default_factory=list)
    available_tools: list[dict[str, Any]] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0


def _read_mcp_response(response: httpx.Response) -> dict:
    ct = response.headers.get("content-type", "")
    if "text/event-stream" in ct:
        for line in response.text.splitlines():
            if line.startswith("data: "):
                data = json.loads(line[6:])
                if "result" in data or "error" in data:
                    return data
        raise RuntimeError(f"SSE stream closed without a result event. Body: {response.text[:500]}")
    return response.json()


DEFAULT_LIVE_MCP_URL = "http://127.0.0.1:5001/mcp/v1"
MOCK_MCP_URL = "mock://earthdata-mcp"
MOCK_RESPONSES_KEY = "mock_tool_responses"


def _live_mcp_url() -> str:
    return os.getenv("MCP_SERVER_URL", DEFAULT_LIVE_MCP_URL)


def _resolve_mcp_target(metadata: dict[str, Any] | None) -> tuple[str, str]:
    """Return (url, mock_responses_json) for a dataset item.

    Items whose metadata defines `mock_tool_responses` run in mock mode: the url
    is the `mock://` sentinel and the responses are serialized so they become part
    of the `_bedrock_agent_task` cache key. The task and every evaluator must call
    this with the item's metadata so they all hit the same cache entry.
    """
    if isinstance(metadata, dict) and MOCK_RESPONSES_KEY in metadata:
        return MOCK_MCP_URL, json.dumps(metadata[MOCK_RESPONSES_KEY], sort_keys=True)
    return _live_mcp_url(), ""


class _MockToolsCallTransport(httpx.BaseTransport):
    """Pass everything through to the live server except `tools/call`.

    `initialize`, `notifications/initialized` and `tools/list` are forwarded to the
    live MCP server so the model sees the real tool schemas. `tools/call` is answered
    from `mock_responses`, which maps tool name to either one payload (returned for
    every call) or a list of payloads (the nth call gets the nth entry).
    """

    def __init__(self, mock_responses: dict[str, Any], live_url: str):
        self._mock_responses = mock_responses
        self._live_url = live_url
        self._live = httpx.HTTPTransport()
        self._call_counts: dict[str, int] = {}

    def close(self) -> None:
        self._live.close()

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if body.get("method") != "tools/call":
            return self._forward(request)

        params = body.get("params") or {}
        name = params.get("name", "")
        count = self._call_counts.get(name, 0)
        self._call_counts[name] = count + 1

        result = self._mock_result(name, count)
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": body.get("id"), "result": result})

    def _forward(self, request: httpx.Request) -> httpx.Response:
        headers = {
            k: v for k, v in request.headers.items() if k.lower() not in ("host", "content-length")
        }
        live_request = httpx.Request(
            request.method, self._live_url, headers=headers, content=request.content
        )
        response = self._live.handle_request(live_request)
        response.read()
        return response

    def _mock_result(self, name: str, call_index: int) -> dict[str, Any]:
        if name not in self._mock_responses:
            return _mock_error(f"No mock response defined for tool '{name}'")

        configured = self._mock_responses[name]
        if isinstance(configured, list):
            if call_index >= len(configured):
                return _mock_error(
                    f"Mock responses for tool '{name}' exhausted: call "
                    f"{call_index + 1} but only {len(configured)} defined"
                )
            payload = configured[call_index]
        else:
            payload = configured

        text = payload if isinstance(payload, str) else json.dumps(payload)
        return {"content": [{"type": "text", "text": text}], "isError": False}


def _mock_error(message: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": message}], "isError": True}


def _make_call_tool_result(content: list[dict], is_error: bool) -> CallToolResult:
    items = []
    for c in content:
        if c.get("type") == "text":
            items.append(TextContent(type="text", text=c.get("text", "")))
        else:
            items.append(TextContent(type="text", text=json.dumps(c)))
    return CallToolResult(content=items, isError=is_error)


@cache
@observe(as_type="generation")
def _bedrock_agent_task(
    question: str, url: str, model_id: str, mock_responses_json: str = ""
) -> _AgentResult:
    """Synchronous agentic loop: Bedrock picks tools, httpx calls the MCP server.

    When `url` is the `mock://` sentinel, `tools/call` is answered from
    `mock_responses_json` and everything else goes to the live server.
    """
    is_mock = url == MOCK_MCP_URL
    client_kwargs: dict[str, Any] = {}
    if is_mock:
        client_kwargs["transport"] = _MockToolsCallTransport(
            json.loads(mock_responses_json or "{}"), _live_mcp_url()
        )
    max_turns = int(os.getenv("BEDROCK_MAX_TURNS", str(DEFAULT_BEDROCK_MAX_TURNS)))
    region = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1"))

    req_headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }

    with httpx.Client(timeout=60, **client_kwargs) as http:
        init_resp = http.post(
            url,
            headers=req_headers,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "regression-test", "version": "1.0"},
                },
            },
        )
        init_resp.raise_for_status()
        session_id = init_resp.headers.get("mcp-session-id", "")
        init_data = _read_mcp_response(init_resp)
        server_instructions = (init_data.get("result") or {}).get("instructions") or ""

        sh = {**req_headers, **({"mcp-session-id": session_id} if session_id else {})}

        http.post(
            url,
            headers=sh,
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
        )

        tools_resp = http.post(
            url,
            headers=sh,
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        )
        tools_resp.raise_for_status()
        tools_data = _read_mcp_response(tools_resp)
        available_tools: list[dict] = (tools_data.get("result") or {}).get("tools", [])

        bedrock_tool_config = {
            "tools": [
                {
                    "toolSpec": {
                        "name": t["name"],
                        "description": t.get("description", ""),
                        "inputSchema": {"json": t.get("inputSchema", {})},
                    }
                }
                for t in available_tools
            ]
        }

        bedrock = boto3.client("bedrock-runtime", region_name=region)
        messages: list[dict] = [{"role": "user", "content": [{"text": question}]}]
        invocations: list[_ToolInvocation] = []
        call_id = 10
        total_input_tokens = 0
        total_output_tokens = 0

        for _ in range(max_turns):
            response = bedrock.converse(
                modelId=model_id,
                **({"system": [{"text": server_instructions}]} if server_instructions else {}),
                messages=messages,
                toolConfig=bedrock_tool_config,
            )

            stop_reason = response["stopReason"]
            assistant_message = response["output"]["message"]
            messages.append(assistant_message)
            usage = response.get("usage", {})
            total_input_tokens += usage.get("inputTokens", 0)
            total_output_tokens += usage.get("outputTokens", 0)

            if stop_reason != "tool_use":
                break

            tool_results = []
            for block in assistant_message["content"]:
                if "toolUse" not in block:
                    continue
                tool_use = block["toolUse"]
                tool_name = tool_use["name"]
                tool_args = tool_use["input"]
                tool_use_id = tool_use["toolUseId"]

                started = time.monotonic()
                call_resp = http.post(
                    url,
                    headers=sh,
                    json={
                        "jsonrpc": "2.0",
                        "id": call_id,
                        "method": "tools/call",
                        "params": {"name": tool_name, "arguments": tool_args},
                    },
                )
                call_resp.raise_for_status()
                call_data = _read_mcp_response(call_resp)
                finished = time.monotonic()
                call_id += 1

                result = call_data.get("result") or {}
                content: list[dict] = result.get("content", [])
                is_error: bool = result.get("isError", False)

                invocations.append(
                    _ToolInvocation(
                        name=tool_name,
                        args=tool_args,
                        output=content,
                        mcp_result=_make_call_tool_result(content, is_error),
                        start_time=started,
                        end_time=finished,
                        is_error=is_error,
                    )
                )
                tool_results.append(
                    {
                        "toolResult": {
                            "toolUseId": tool_use_id,
                            "content": [{"text": json.dumps(content, default=str)}],
                        }
                    }
                )

            messages.append({"role": "user", "content": tool_results})

        final_output: Any = invocations[-1].output if invocations else ""
        last_assistant = next((m for m in reversed(messages) if m.get("role") == "assistant"), None)
        if last_assistant:
            texts = [b.get("text", "") for b in last_assistant.get("content", []) if "text" in b]
            if texts:
                final_output = " ".join(texts)

        get_client().update_current_generation(
            model=model_id,
            metadata={"mcp_mode": "mock" if is_mock else "live"},
            usage_details={"input": total_input_tokens, "output": total_output_tokens},
        )

        return _AgentResult(
            final_output=final_output,
            invocations=invocations,
            available_tools=available_tools,
            input_tokens=total_input_tokens,
            output_tokens=total_output_tokens,
        )
