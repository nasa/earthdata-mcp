"""Environment utility for resolving the current deployment environment."""

import os


def get_environment() -> str:
    """
    Return the current deployment environment name.

    Reads ``ENVIRONMENT_NAME``, which is injected by Terraform at deploy time.
    Use ``test`` in CI/CD pipelines. Defaults to ``local`` when the variable
    is not set (e.g. local development without a configured ``.env`` file).

    Returns:
        Environment name string (e.g. ``uat``, ``prod``, ``test``, ``local``)
    """
    return os.environ.get("ENVIRONMENT_NAME", "local")


def get_client_id(app: str = "mcp") -> str:
    """
    Build an EED client identifier for the given application.

    Format: ``eed-{environment}-{app}``

    Args:
        app: Application name suffix (default: ``mcp``)

    Returns:
        Client ID string (e.g. ``eed-uat-mcp``)
    """
    return f"eed-{get_environment()}-{app}"
