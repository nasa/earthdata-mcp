# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commonly Used Commands

This project uses `uv` for dependency management and running commands.

### Development Server
- **Run local server:** `uv run server.py http` (Starts the FastMCP server at `http://127.0.0.1:5001/mcp/v1`)
- **Inspector:** `npx @modelcontextprotocol/inspector` (Connects to `http://localhost:5001/mcp/v1` using Streamable HTTP transport)

### Testing
- **Run all tests:** `uv run pytest`
- **Run a specific test file:** `uv run pytest tests/test_server.py`
- **Run tests with verbose output:** `uv run pytest -v`

### Linting and Formatting
- **Format code:** `uv run ruff format .`
- **Lint and fix:** `uv run ruff check . --fix`
- **Run pylint:** `uv run pylint util/ tests/ lambdas/ tools/ prompts/ models/ server.py loader.py`
- **Run pre-commit hooks on staged files:** `uv run pre-commit run`

## High-Level Architecture

The Earthdata MCP server provides LLM agents with direct access to NASA's Common Metadata Repository (CMR) via the Model Context Protocol (MCP).

### Core Components
- **`server.py`**: The main entry point that initializes the `FastMCP` server and handles routing.
- **`loader.py`**: Dynamically discovers and loads tools from the `tools/` directory.
- **`tools/`**: Contains self-contained MCP tools (`get_collections`, `get_granules`, `get_services`, `get_tools`).
  - Each tool requires a `manifest.json` (defining name, description, version, etc.) and a `tool.py` containing the entry function.
  - Tools optionally define their output schema using a Pydantic model in `output_model.py`.
- **`prompts/`**: Contains system instructions (`instructions.py`) that enforce the core agent workflow: **Discover** (`get_collections`) → **Verify** (`get_granules`) → **Access** (via the `earthaccess` Python library).
- **`models/`**: Centralized Pydantic models for standardizing CMR API responses and tool inputs.
- **`lambdas/` & `discover_data` (Legacy)**: Ingestion and embedding pipelines that are actively being deprecated in favor of direct, real-time CMR API integrations.

### Agent Workflow
When modifying or adding features, remember the intended LLM workflow:
1. **Discover**: Find collections using spatial/temporal or keyword constraints.
2. **Verify**: Check for actual data files (granules) to confirm coverage.
3. **Access**: Provide users with code snippets using the `earthaccess` library for authentication and download.

### Documentation Maintenance
When adding new tools, changing existing behavior, or modifying the architecture, ensure that documentation is kept up-to-date:
- **`README.md`**: Update core project information, available tools, and top-level instructions.
- **`docs/`**: This directory contains extensive documentation separated by audience:
  - **`docs/consumers/`**: User-facing documentation on how to connect and use the server.
  - **`docs/developers/`**: Architecture diagrams, local development guides, troubleshooting, and deployment runbooks.

## Commit Conventions

When drafting commit messages, please follow this pattern if applicable:
`[Jira Ticket]: [Brief Description]` (e.g., `CMRNLP-123: Add new spatial tool`)

**Important Note for External Contributors:**
This project uses Jira for internal issue tracking. If you are an external contributor or do not have a Jira ticket, simply use a standard descriptive commit message without the prefix (e.g., `Add new spatial tool`). Claude Code should check if the current branch name contains a Jira ticket (like `CMRNLP-XXX`) and use that automatically; otherwise, it should omit the prefix.
