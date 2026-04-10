# Earthdata MCP Server Documentation

This directory contains detailed documentation for both consumers of the MCP server and developers maintaining the infrastructure.

## For Consumers (`docs/consumers/`)

*(Coming soon)* This section will contain examples, sample prompts, and advanced guides for LLM agents and human developers querying the Common Metadata Repository (CMR) via this MCP server.

## For Developers (`docs/developers/`)

Developer guidelines and procedures for contributing to and maintaining the application.

- **[Adding a New Tool](developers/adding-a-new-tool.md)**: How to build and register a new tool, configure `manifest.json`, follow Semantic Versioning, and update Dockerfiles.
- **[Adding an Environment Variable](developers/adding-an-env-var.md)**: The exact files to touch in Terraform, Docker, and Bamboo when adding a new environment variable to the ECS container.
- **[Versioning Methodology](developers/versioning.md)**: Explains the decoupled versioning strategy between the MCP Server (`pyproject.toml`) and individual tools (`manifest.json`).
- **[Troubleshooting Deployments](developers/troubleshooting-deployments.md)**: Step-by-step instructions for debugging a `503 Service Unavailable` error, finding AWS CloudWatch logs, and fixing crash loops.
