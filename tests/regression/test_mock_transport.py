"""Unit tests for the tools/call mock transport used by the mocked regression dataset."""

import json

import httpx

from evals.sandbox_agent import (
    MOCK_MCP_URL,
    _MockToolsCallTransport,
    _resolve_mcp_target,
)

LIVE_URL = "http://live.example/mcp/v1"


def _client(mock_responses):
    transport = _MockToolsCallTransport(mock_responses, LIVE_URL)
    seen: list[httpx.Request] = []

    def live_handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": 2, "result": {"tools": []}})

    transport._live = httpx.MockTransport(live_handler)
    return httpx.Client(transport=transport), seen


def _call(client, name, call_id=10):
    resp = client.post(
        MOCK_MCP_URL,
        json={
            "jsonrpc": "2.0",
            "id": call_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": {}},
        },
    )
    return resp.json()


def test_non_tool_calls_are_forwarded_to_live_url():
    client, seen = _client({})
    resp = client.post(
        MOCK_MCP_URL,
        headers={"mcp-session-id": "abc"},
        json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
    )
    assert resp.json()["result"] == {"tools": []}
    assert str(seen[0].url) == LIVE_URL
    assert seen[0].headers["mcp-session-id"] == "abc"


def test_single_payload_is_returned_for_every_call_and_wrapped():
    client, seen = _client({"tool_a": {"status": "ok"}})
    for call_id in (10, 11):
        data = _call(client, "tool_a", call_id)
        assert data["id"] == call_id
        assert data["result"]["isError"] is False
        assert json.loads(data["result"]["content"][0]["text"]) == {"status": "ok"}
    assert seen == []


def test_list_payload_returns_nth_response_then_errors_when_exhausted():
    client, _ = _client({"tool_a": [{"n": 1}, {"n": 2}]})
    assert json.loads(_call(client, "tool_a")["result"]["content"][0]["text"]) == {"n": 1}
    assert json.loads(_call(client, "tool_a")["result"]["content"][0]["text"]) == {"n": 2}
    third = _call(client, "tool_a")["result"]
    assert third["isError"] is True
    assert "exhausted" in third["content"][0]["text"]


def test_missing_mock_returns_error_result():
    client, _ = _client({"tool_a": {}})
    result = _call(client, "tool_b")["result"]
    assert result["isError"] is True
    assert "tool_b" in result["content"][0]["text"]


def test_resolve_target_uses_mock_only_when_metadata_defines_responses(monkeypatch):
    monkeypatch.setenv("MCP_SERVER_URL", LIVE_URL)
    assert _resolve_mcp_target({"expected_tool_call": "x"}) == (LIVE_URL, "")
    assert _resolve_mcp_target(None) == (LIVE_URL, "")
    url, key = _resolve_mcp_target({"mock_tool_responses": {"b": 1, "a": 2}})
    assert url == MOCK_MCP_URL
    assert key == '{"a": 2, "b": 1}'
