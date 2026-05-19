# Integration Testing

The `scripts/integration_test.py` is a developer tool for validating the end-to-end functionality of the Earthdata MCP Server against a live Common Metadata Repository (CMR) backend.

**Note:** This is strictly a developer utility for manual verification of complex search features (pagination cursors, field filtering, response parsing). It is *not* intended to be run in CI/CD pipelines to avoid hitting production CMR endpoints unnecessarily.

## What it tests

The script verifies:

1. **Pagination:** Ensures `limit`, `cursor`, and `next_cursor` behave correctly across all 7 tools.
2. **Field filtering:** Validates that `fields` parameters successfully trim response payloads while preserving mandatory fields (e.g. `concept_id`).
3. **Parameter fidelity:** Verifies new and complex search parameters (like spatial bounding boxes, `has_granules`, sorting).
4. **Data extraction:** Checks that the tools parse the CMR JSON payloads correctly and map them to the MCP output schemas.

## Usage

Start your local MCP server:

```bash
uv run uvicorn server:app --port 5001
```

In a separate terminal, run the test script:

```bash
uv run python scripts/integration_test.py
```

To run against a specific server URL:

```bash
uv run python scripts/integration_test.py --url http://localhost:5001/mcp/v1
```

## How it works

The script connects to the MCP server via SSE (Server-Sent Events) HTTP transport using the `mcp` client SDK. It sequentially calls MCP tools (`call_tool`) and asserts the expected structure, count, and content of the returned items.
