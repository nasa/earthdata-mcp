# Earthdata MCP Server Documentation

This directory contains detailed documentation for both consumers of the MCP server and developers maintaining the infrastructure.

## For Consumers (`docs/consumers/`)

This section contains examples, sample prompts, and advanced guides for LLM agents and human developers querying NASA's Earth science data APIs via this MCP server. Every tool available today is backed by the Common Metadata Repository (CMR).

- **[User Guide](consumers/earthdata-mcp-server-user-guide.md)**: How to connect to the MCP server using variety of harnesses, example walkthrough, troubleshooting, and feedback reporting.
- **[Currently Supported Parameters](consumers/supported-parameters.md)**: maps Earthdata MCP tool parameters to the upstream API arguments and schema fields behind them.

## For Developers (`docs/developers/`)

Developer guidelines and procedures for contributing to and maintaining the application.

- **[Adding a New Tool](developers/adding-a-new-tool.md)**: How to build and register a new tool, configure `manifest.json`, follow Semantic Versioning, and update Dockerfiles.
- **[Adding Authentication to a Tool](developers/adding-authentication-to-a-tool.md)**: How to configure a tool to require authentication, including updating the manifest and handling OAuth scopes.
- **[Adding an Environment Variable](developers/adding-an-env-var.md)**: The exact files to touch in Terraform, Docker, and Bamboo when adding a new environment variable to the ECS container.
- **[Versioning Methodology](developers/versioning.md)**: Explains the decoupled versioning strategy between the MCP Server (`pyproject.toml`) and individual tools (`manifest.json`).
- **[Troubleshooting Deployments](developers/troubleshooting-deployments.md)**: Step-by-step instructions for debugging a `503 Service Unavailable` error, finding AWS CloudWatch logs, and fixing crash loops.
- **[Integration Testing](developers/integration-testing.md)**: Instructions for running the manual integration test script against live CMR environments.

## Public documentation site

The public site is an Astro + Starlight project at `docs/site/`, published to
[nasa.github.io/earthdata-mcp](https://nasa.github.io/earthdata-mcp/). It renders
the existing consumer Markdown files (`docs/consumers/*.md`) and `docs/index.mdx`
directly, so there's no duplication: the same files that render in the GitHub
repo view also render on the site. Update those source files rather than
copying the guide into a second format. Developer and infrastructure guides
remain available on GitHub and are not included in the public site build.

### Running it locally

Node 26 is required (`docs/site/.nvmrc`). Run from `docs/site`:

```sh
npm install
npm run dev     # dev server at http://localhost:4321/earthdata-mcp/
npm run build   # static build into dist/, no dev server
npm run check   # astro check: types and template diagnostics
npm run test    # vitest unit tests
```

### Adding a page

Content is pulled in by the glob loader in `src/content.config.ts`, which matches
`docs/index.mdx` and `docs/consumers/**/*.md`. A file outside those paths will
not appear on the site. Every page needs Starlight frontmatter with a `title:`
field, not Quarto's `pagetitle:`. Add the page to the `sidebar` array in
`astro.config.mjs` to give it a nav entry.

Internal links are written with the `/earthdata-mcp` base prefix, since the site
deploys to a GitHub Pages project subpath rather than a domain root.

### Horizon design system

The site uses NASA's Horizon design system
([`@nasa-terra/components`](https://github.com/nasa/terra-ui-components)), so its look matches terra-ui rather than stock
Starlight. The pieces:

- `src/components/Head.astro` registers the Horizon web components the site uses
  and mirrors Starlight's `data-theme` onto Horizon's `data-mode`, which is how
  the light and dark schemes stay in sync.
- `src/components/Header.astro` replaces Starlight's header with
  `terra-site-header`, keeping Starlight's own search, social icons, and theme
  toggle slotted inside it.
- `src/styles/horizon.css` maps Starlight's `--sl-*` variables onto Horizon
  tokens. Anything that exists because of Horizon belongs here.
- `src/styles/custom.css` holds plain Starlight overrides that would apply with
  or without Horizon.
- `src/components/ServerStatus.astro` polls the MCP server's health endpoint from
  the visitor's browser and renders a status indicator on the home page. Under
  `npm run dev` it points at `http://127.0.0.1:5001/mcp/health`, so start the
  server with `uv run server.py http` or the badge reports "Unreachable".

Logic worth testing lives in `src/lib/` with colocated `*.test.ts` files, so the
components stay thin enough to verify by eye.

### Deployment

Pull requests build a downloadable `github-pages` artifact without deploying.
After merge, changes to documentation or the package version rebuild and publish
from `main`. A maintainer must first select **GitHub Actions** as the source under
**Settings > Pages**. The deployment then publishes to
`https://nasa.github.io/earthdata-mcp/`; the workflow does not change repository
settings or publish from forks.
