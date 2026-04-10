# Versioning Methodology

The Earthdata MCP server uses a decoupled versioning strategy. We maintain two distinct version concepts: the **Server Version** and the **Tool Version**.

This separation allows us to continuously deploy infrastructure improvements, bug fixes, or entirely new tools without triggering breaking-change alerts for clients who rely on stable, existing tools.

## 1. The MCP Server Version (`pyproject.toml`)

This is the semantic version of the entire Python package and infrastructure. It is the version the server advertises to connecting MCP clients during the initialization handshake.

### How it works

- The single source of truth is the `version` field in `pyproject.toml`.
- The application reads its own version dynamically at runtime via `importlib.metadata` in `server.py`.
- The CI/CD pipeline does **not** inject version strings via environment variables or Terraform.

### When to bump

- **Major**: Core framework upgrades (e.g., FastMCP v2 -> v3), breaking changes to the connection protocol, or dropping support for major features.
- **Minor**: Adding a completely new tool, or significant new non-breaking features.
- **Patch**: Infrastructure changes, dependency updates, or internal refactoring that does not change the LLM-facing interface.

## 2. Individual Tool Versions (`manifest.json`)

Every tool in the `tools/` directory has its own `manifest.json` containing a strictly required `version` string following Semantic Versioning (SemVer).

This version tells the LLM (and the connecting client software) exactly what interface to expect.

### When to bump

You MUST bump a tool's version when changing its LLM-facing interface or behavior:

- **Major (`x.0.0`)**: Breaking changes to the interface. Examples:
  - Removing an input parameter.
  - Renaming an output field.
  - Fundamentally changing the tool's purpose.
- **Minor (`x.y.0`)**: Backwards-compatible additions. Examples:
  - Adding an optional input parameter.
  - Adding a new field to the output JSON.
- **Patch (`x.y.z`)**: Internal bug fixes or performance improvements that do not change the tool's inputs, outputs, or expected behavior.
