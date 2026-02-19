"""Environment utility for resolving the current deployment environment."""

import os


def get_environment() -> str:
    """
    Return the current deployment environment name.

    Reads ``ENVIRONMENT_NAME``, which is injected by Terraform at deploy time.
    Use ``test`` in CI/CD pipelines. Defaults to ``development`` when the variable
    is not set (e.g. local development without a configured ``.env`` file).

    Returns:
        Environment name string (e.g. ``uat``, ``prod``, ``test``, ``development``)
    """
    return os.environ.get("ENVIRONMENT_NAME", "development")


def get_client_id() -> str:
    """
    Build an client identifier for the given application.

    Format: ``eed-{environment}-mcp``

    Returns:
        Client ID string (e.g. ``eed-uat-mcp``)
    """
    return f"eed-{get_environment()}-mcp"
