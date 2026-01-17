# earthdata-mcp

MCP (Model Context Protocol) server for NASA Earthdata with semantic search capabilities powered by embeddings.

## Project Structure

```
earthdata-mcp/
├── tools/                    # MCP tools (self-contained)
│   └── <toolname>/
│       ├── tool.py           # Tool implementation
│       ├── manifest.json     # MCP tool metadata
│       ├── input_model.py    # Pydantic input model
│       └── output_model.py   # Pydantic output model
├── lambdas/                  # AWS Lambda handlers
│   ├── ingest/               # SNS to SQS message processing
│   ├── embedding/            # Embedding generation
│   └── bootstrap/            # Initial data load
├── util/                     # Shared utilities
├── middleware/               # Server middleware (CORS)
├── terraform/                # Infrastructure as code
│   ├── database/             # RDS PostgreSQL stack
│   └── application/          # Lambdas, ECS, SQS stack
├── server.py                 # MCP server entry point
├── loader.py                 # Tool discovery and registration
└── pyproject.toml            # Dependencies
```

## Quick Start

### Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) package manager

### Installation

```bash
# Clone and enter directory
git clone <repo-url>
cd earthdata-mcp

# Install dependencies
uv sync

# Install dev dependencies (for testing)
uv sync --extra dev
```

### Running Locally

**HTTP Mode (recommended for development):**

```bash
uv run server.py http
```

Server runs at `http://127.0.0.1:5001/mcp`

**STDIO Mode (for AI integrations):**

```bash
uv run server.py stdio
```

See [FastMCP integrations](https://gofastmcp.com/integrations) for connecting to Claude, VS Code, etc.

## Testing

```bash
# Run all tests
uv run pytest

# Run with verbose output
uv run pytest -v

# Run specific test file
uv run pytest tests/test_server.py
```

### MCP Inspector (Interactive Testing)

1. Start the server:
   ```bash
   uv run server.py http
   ```

2. Launch inspector:
   ```bash
   npx @modelcontextprotocol/inspector
   ```

3. Connect at `http://localhost:6274`:
   - Transport Type: **Streamable HTTP**
   - URL: `http://localhost:5001/mcp`

## Adding a New Tool

1. Create folder under `tools/<toolname>/`

2. Add required files:
   - `manifest.json` - Tool metadata with `"entry"` function name
   - `tool.py` - Implementation with async function
   - `input_model.py` - Pydantic input validation
   - `output_model.py` - Pydantic output model

3. The tool is automatically discovered by `loader.py`

4. Test with MCP Inspector, then add pytest under `tests/`

## Deployment

The application deploys to AWS via Bamboo CI/CD:

- **MCP Server**: ECS Fargate behind ALB at `/mcp`
- **Lambdas**: Ingest (SNS to SQS), Embedding (Bedrock), Bootstrap
- **Database**: RDS PostgreSQL with pgvector

### Environment Variables

| Variable | Description |
|----------|-------------|
| `ENVIRONMENT_NAME` | Deployment environment (sit, uat, prod) |
| `CMR_URL` | CMR API base URL |
| `EMBEDDING_MODEL` | Bedrock model ID |

## Connecting Clients

Once deployed, connect MCP clients to:

```
https://cmr.earthdata.nasa.gov/mcp/sse
```

Works with:
- Claude Code CLI
- VS Code MCP extensions
- Any MCP-compatible client

## Troubleshooting

**Import errors**: Ensure virtual environment is activated

**Tool not found**: Check `manifest.json` has valid `"entry"` field

**Connection refused**: Verify server is running on correct port
