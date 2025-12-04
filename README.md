# earthdata-mcp
# MCP Server — Project Overview

This repository implements a modular MCP (Model Context Protocol) server with support for multiple transport modes (STDIO, HTTP, SSE). Tools are organized under the `tools/` directory, and each tool is self-contained with its own Python implementation and manifest.

## Project Structure

```
mcp/
│
├── tools/                 # All MCP tools live here
│   └── <toolname>/        # Each tool is fully self-contained
│       ├── tool.py        # Python implementation of the tool
│       ├── manifest.json  # MCP tool metadata (incl. entry function)
│
├── tests/                 # All Pytest test files live here
│   ├── test_<tool>.py
│
├── util/                 # Any utility functions common to all tools.
│
├── loader.py              # Discovers tools, loads manifest, registers functions
├── server.py              # Entry point for STDIO / HTTP / SSE server
├── pyproject.toml         # Dependencies & project configuration
└── README.md              # This file
```

## Quick Start

### Installation

1. **Clone the repository and navigate to the MCP folder:**
   ```bash
   cd mcp
   ```

2. **Create and activate virtual environment:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   uv sync
   ```

## Running the MCP Server

The server supports three primary modes: **STDIO**, **HTTP**, and **SSE**.

### HTTP Mode (Development & Testing)

Run the server as a web server using Uvicorn:

```bash
PYTHONPATH=.. uv run server.py http
```

- `PYTHONPATH=..` ensures imports work from project root
- `http` tells the server to run in HTTP mode
- Server runs at `http://127.0.0.1:5001/mcp`

### STDIO Mode (Chainlit Integration)

Run the server so can use your tools:

1. **Navigate to the mcp/ folder:**
   ```bash
   cd mcp
   ```

2. **Activate your virtual environment:**
   ```bash
   source .venv/bin/activate
   ```

3. **Install the server into Claude Desktop:**
   ```bash
   fastmcp install claude-desktop server.py --project .
   ```

4. **Verify installation:**
   - Open Claude Desktop
   - Start a new conversation
   - Your tools should appear in the tools menu

### SSE Mode

For Server-Sent Events support:
```bash
PYTHONPATH=.. uv run server.py sse
```

## Adding New Tools

### 1. Create Tool Structure

Create a folder under `tools/`:

```
tools/
└── my_new_tool/
    ├── tool.py
    ├── manifest.json
```

### 2. Write manifest.json

This declares the tool and its metadata:

```json
{
  "name": "my_new_tool",
  "description": "Does something interesting",
  "version": "1.0.0",
  "tags": ["example", "utility"],
  "entry": "my_new_tool"   // The function name inside tool.py
}
```


### 3. Write tool.py

Implement the tool with a `register(mcp)` function:

```python
from pydantic import BaseModel
from typing import Any

class MyInput(BaseModel):
    input_text: str
    optional_param: int | None = None

async def my_new_tool(params: MyInput) -> Any:
    return [f"You sent: {params.input_text}"]
```

## Testing

### Run All Tests

```bash
pytest
```

### Test File Structure

All tests now live in:
```bash
mcp/tests/test_*.py
```

### Example Pytest
```python
import pytest
from mcp.server.fastmcp import FastMCP
from tools.my_new_tool.tool import my_new_tool, MyInput

@pytest.mark.asyncio
async def test_my_new_tool_direct():
    result = await my_new_tool(MyInput(input_text="Hello"))
    assert "Hello" in result[0]

@pytest.mark.asyncio
async def test_my_new_tool_via_mcp():
    mcp = FastMCP("test_server")
    mcp.register_tool("my_new_tool", my_new_tool)

    result = await mcp.call_tool("my_new_tool", {"input_text": "Test"})
    assert result
```

### Test via MCP Inspector (Interactive Testing) (RECOMMENDED)

The MCP Inspector provides a visual interface for testing tools:

1. **Start the MCP server in HTTP mode:**
   ```bash
   PYTHONPATH=.. uv run server.py http
   ```

2. **Launch MCP Inspector:**
   ```bash
   npx @modelcontextprotocol/inspector
   ```
   Opens at `http://localhost:6274`

3. **Connect to your MCP server:**
   * Streamable HTTP
    - **Transport Type:** Streamable HTTP
    - **URL:** `http://localhost:5001/mcp`
    - **Connection Type:** Direct
   * STDIO
    - **Transport Type:** STDIO
    - **Command:** uv
    - **Arguments:** run server.py stdio

4. **Test your tools:**
   - Click "List Tools" to see all available tools
   - Select a tool to test
   - Enter input parameters
   - Click "Run Tool"
   - Debug errors and validate output

### Test via Chainlit Application

Test your tools in a chat interface:

1. **Navigate to the chat application:**
   ```bash
   cd ../chat
   ```

2. **Activate Chainlit environment:**
   ```bash
   source .chainlit/bin/activate
   ```

3. **Run the Chainlit app:**
   ```bash
   NOMINATIM_USER_AGENT=chainlit chainlit run app.py -w
   ```

4. **Connect to MCP in browser:**
   - Open `http://localhost:8000`
   - Click the tools icon (🔧)
   - Click "Connect an MCP"
   - Enter settings:
     - **Type:** streamable-http
     - **Name:** cmr-mcps
     - **HTTP URL:** `http://localhost:5001/mcp`

5. **Your tools will appear under "Tools" menu**

## How Tools Get Loaded

`loader.py` automatically:
1. Scans the `tools/` directory
2. Validates each `manifest.json`
3. Imports the tool's `tool.py`
4. Loads the function specified in "entry"
5. Registers it with the MCP server

**No manual configuration needed!** Just add your tool folder and it's automatically discovered.

## Troubleshooting

### Import Errors

- Ensure `PYTHONPATH=..` is set when running
- Check all dependencies are installed
- Verify virtual environment is activated

## Contributing

When adding a new tool:

1. ✅ Follow the folder structure
2. ✅ Include `manifest.json` and `tool.py`
3. ✅ Ensure manifest specifies "entry"
4. ✅ Write pytest files under tests/
5. ✅ Test with MCP Inspector
6. ✅ Run pytest before committing