# Earthdata MCP Server Documentation

This directory contains detailed documentation for both consumers of the MCP server and developers maintaining the infrastructure.

## For Consumers (`docs/consumers/`)

This section contains examples, sample prompts, and advanced guides for LLM agents and human developers querying the Common Metadata Repository (CMR) via this MCP server.

- **[User Guide](consumers/earthdata-mcp-server-user-guide.md)**: How to connect to the MCP server using variety of harnesses, example walkthrough, troubleshooting, and feedback reporting.
- **[Currently Supported Parameters](consumers/supported-parameters.md)**: maps Earthdata MCP tool parameters to their corresponding CMR API arguments and underlying UMM schema paths.

## For Developers (`docs/developers/`)

Developer guidelines and procedures for contributing to and maintaining the application.

- **[Adding a New Tool](developers/adding-a-new-tool.md)**: How to build and register a new tool, configure `manifest.json`, follow Semantic Versioning, and update Dockerfiles.
- **[Adding an Environment Variable](developers/adding-an-env-var.md)**: The exact files to touch in Terraform, Docker, and Bamboo when adding a new environment variable to the ECS container.
- **[Versioning Methodology](developers/versioning.md)**: Explains the decoupled versioning strategy between the MCP Server (`pyproject.toml`) and individual tools (`manifest.json`).
- **[Troubleshooting Deployments](developers/troubleshooting-deployments.md)**: Step-by-step instructions for debugging a `503 Service Unavailable` error, finding AWS CloudWatch logs, and fixing crash loops.
- **[Integration Testing](developers/integration-testing.md)**: Instructions for running the manual integration test script against live CMR environments.

## Public documentation site

The Quarto project renders the existing consumer Markdown files directly, together
with `index.qmd`. Update those source files rather than copying the guide into a
second format. Developer and infrastructure guides remain available on GitHub and
are not included in the public site build.

Install Quarto 1.10.18, matching `.github/workflows/docs.yml`, then run from
the repository root:

```sh
quarto preview docs
# Build without starting a local server:
quarto render docs
```

No Python environment, credentials, or live data queries are needed to render the
site. Examples are displayed without execution. Generated files under `docs/_site`
and `docs/.quarto` are ignored by Git.

Pull requests build a downloadable `github-pages` artifact without deploying.
After merge, changes to documentation or the package version rebuild and publish
from `main`. A maintainer must first select **GitHub Actions** as the source under
**Settings > Pages**. The deployment then publishes to
`https://nasa.github.io/earthdata-mcp/`; the workflow does not change repository
settings or publish from forks.
