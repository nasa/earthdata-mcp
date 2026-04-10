---
globs: "**/*.md"
description: Enforces clean, standard Markdown formatting that complies with
  common markdownlint configurations to prevent CI/CD linting failures.
alwaysApply: true
---

# Markdown Lint Standards

Always strictly follow standard `markdownlint` rules when generating or editing Markdown files. Specifically:

1. Ensure fenced code blocks are surrounded by blank lines (MD031).
2. Ensure lists are surrounded by blank lines (MD032).
3. Do not leave trailing spaces at the ends of lines (MD009).
4. Avoid multiple consecutive blank lines (MD012).
5. Ensure headings have exactly one space after the `#` (MD018).
6. Do not use bare URLs; wrap them in angle brackets `<url>` or standard link format (MD034).
7. Follow hierarchy rules like starting files with an h1
