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
from mcp.types import CallToolResult, TextContent

load_dotenv()

DEFAULT_MAX_TURNS = 5


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


def _read_mcp_response(response: httpx.Response) -> dict:
    ct = response.headers.get("content-type", "")
    if "text/event-stream" in ct:
        for line in response.text.splitlines():
            if line.startswith("data: "):
                data = json.loads(line[6:])
                if "result" in data or "error" in data:
                    return data
        raise RuntimeError(
            f"SSE stream closed without a result event. Body: {response.text[:500]}"
        )
    return response.json()


def _make_call_tool_result(content: list[dict], is_error: bool) -> CallToolResult:
    items = []
    for c in content:
        if c.get("type") == "text":
            items.append(TextContent(type="text", text=c.get("text", "")))
        else:
            items.append(TextContent(type="text", text=json.dumps(c)))
    return CallToolResult(content=items, isError=is_error)


@cache
def _bedrock_agent_task(question: str, url: str, model_id: str) -> _AgentResult:
    """Synchronous agentic loop: Bedrock picks tools, httpx calls the MCP server."""
    max_turns = int(os.getenv("BEDROCK_MAX_TURNS", str(DEFAULT_MAX_TURNS)))
    region = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1"))

    req_headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }

    with httpx.Client(timeout=60) as http:
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

        for _ in range(max_turns):
            response = bedrock.converse(
                modelId=model_id,
                **(
                    {"system": [{"text": server_instructions}]}
                    if server_instructions
                    else {}
                ),
                messages=messages,
                toolConfig=bedrock_tool_config,
            )

            stop_reason = response["stopReason"]
            assistant_message = response["output"]["message"]
            messages.append(assistant_message)

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
        last_assistant = next(
            (m for m in reversed(messages) if m.get("role") == "assistant"), None
        )
        if last_assistant:
            texts = [
                b.get("text", "")
                for b in last_assistant.get("content", [])
                if "text" in b
            ]
            if texts:
                final_output = " ".join(texts)

        return _AgentResult(
            final_output=final_output,
            invocations=invocations,
            available_tools=available_tools,
        )
