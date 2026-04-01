# earthdata-mcp

MCP (Model Context Protocol) server for NASA Earthdata.

## Core Capabilities

This MCP server provides LLM agents with direct access to NASA's Common Metadata Repository (CMR).

### Available Tools

- **`get_collections`**: Searches for datasets (collections) using scientific keywords, instruments, platforms, or spatial/temporal constraints.
- **`get_granules`**: Searches for specific data files (granules) within a collection. Used to verify actual data availability for a given time and location.
- **`get_services`**: Discovers data access endpoints (OPeNDAP, Harmony) and visualization layers (WMS/WMTS) associated with a collection.

### Agent Workflow Instructions

The server provides system instructions (`prompts/instructions.py`) that enforce a **Discover → Verify → Access** workflow for LLM clients:

1. **Discover**: Find relevant collections using `get_collections`.
2. **Verify**: Use `get_granules` to confirm data actually exists for the user's requested region/time, as collections often declare global coverage regardless of gaps.
3. **Access**: Instruct users to use the `earthaccess` Python library for authentication and downloading, providing relevant code snippets.

## Project Structure

The repository is structured around a few core domains:

- **`server.py` & `loader.py`**: The FastMCP server entry point and dynamic tool registration logic.
- **`prompts/`**: System prompts and instructions that define the LLM's workflow and persona.
- **`tools/`**: Self-contained MCP tools wrapping NASA CMR APIs (`get_collections`, `get_granules`, `get_services`).
- **`models/`**: Pydantic models for tool input validation and standardized CMR API responses.
- **`tests/`**: Comprehensive test suite (using `pytest`) covering server initialization, tool logic, and mocked CMR API responses.

> **Note on Legacy Code**: The ingestion and embedding pipelines (including the `discover_data` tool, `lambdas/` directory, and associated infrastructure) are currently being deprecated. The architecture is transitioning to rely purely on direct, real-time CMR API integrations.

## For Consumers: Connecting to the Server

The Earthdata MCP server is deployed remotely and communicates via Streamable HTTP. To use the server, you simply need to configure your MCP-compatible client to point to our endpoint.

### Connection URL

Configure your client to connect to the following HTTP endpoint:

```text
https://cmr.earthdata.nasa.gov/mcp
```

Works with:

- Claude Code CLI
- VS Code MCP extensions
- Any MCP-compatible client that supports Streamable HTTP transport

---

## For Developers: Local Environment

If you want to contribute to the server or run it locally, follow these steps.

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

### Starting the Local Server

We recommend running the server in HTTP mode for local development and testing:

```bash
uv run server.py http
```

The server will start and be available at `http://127.0.0.1:5001/mcp`.

### Development & Testing

### Adding a New Tool

1. Create folder under `tools/<toolname>/`
2. Add required files:
   - `manifest.json` - Tool metadata including `"entry_function"` (the name of the callable in `tool.py`), `"name"`, `"description"`, and optional `"enabled"` flag. See `get_services/manifest.json` or `get_granules/manifest.json` for examples.
   - `tool.py` - Implementation as a **synchronous** `def` function whose name matches the `"entry_function"` value in `manifest.json`. `loader.py` wraps it in an async handler automatically; do not use `async def`. See `get_services/tool.py` or `get_granules/tool.py` for examples.
   - `output_model.py` - Pydantic output model (the loader auto-discovers the first `BaseModel` subclass for JSON schema generation).
3. The tool is automatically discovered and registered by `loader.py`.
4. Test with MCP Inspector, then add pytest under `tests/`

### Running Tests

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

### Local Database & Cache Configuration (Legacy)

For local development of the legacy ingestion pipelines, you can run PostgreSQL and Redis locally.

**Database (PostgreSQL):**

1. Start local PostgreSQL (with pgvector extension)
2. Set environment variables in `.env`:

   ```bash
   DB_HOST=localhost
   DATABASE_SECRET_ID=<your-aws-secret-id>  # Still needed for credentials
   ```

**Cache (Redis):**

1. Start local Redis server
2. Set environment variables in `.env`:

   ```bash
   REDIS_HOST=localhost
   REDIS_PORT=6379              # Optional, defaults to 6379
   REDIS_PASSWORD=<password>    # Optional for local dev
   ```

## Deployment

The application deploys to AWS via Bamboo CI/CD:

- **MCP Server**: ECS Fargate behind ALB at `/mcp`
- **Lambdas**: Ingest (SNS to SQS), Embedding (queue consumer), Bootstrap
- **Enrichment Pipeline (Legacy)**: Step Function that validates, fixes, embeds, and stores metadata
- **Database**: RDS PostgreSQL with pgvector
- **Redis**: ElastiCache for caching and payload offloading

See [`terraform/`](terraform/) for infrastructure details and environment variable configuration.

## Troubleshooting

- **Import errors**: Ensure virtual environment is activated
- **Tool not found**: Check `manifest.json` has valid `"entry_function"` field
- **Connection refused**: Verify server is running on correct port
