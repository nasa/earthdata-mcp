# Overview

## What is the feature?

Please summarize the feature or fix.

## What is the Solution?

Summarize what you changed.

## What areas of the application does this impact?

List impacted areas (e.g., specific tools, middleware, infrastructure).

## Testing

### Reproduction steps

- **Tool tested:** (e.g., `get_collections`, `get_granules`)
- **Input payload or query used:**

1. Execute the tool with the provided input.
2. Observe the actual output.
3. Verify the expected output or behavior.

### Attachments

Please include relevant screenshots or files that would be helpful in reviewing and verifying this change.

## Pre-Review Checklist

- [ ] Added automated tests that prove the fix is effective or feature works
- [ ] Verified new and existing unit tests pass locally
- [ ] Performed a self-review of the code
- [ ] Commented code, particularly in hard-to-understand areas
- [ ] Updated corresponding documentation
- [ ] Verified changes generate no new warnings
- [ ] Bumped `pyproject.toml` and `manifest.json` versions according to the [Versioning Methodology](docs/developers/versioning.md) if inputs, outputs, or logic changed
- [ ] Added any new root-level Python directories to `McpServerDockerfile` AND `McpServerDockerfile.dockerignore`
