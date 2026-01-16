"""AWS Secrets Manager client utility."""

import boto3

_client = None


def get_secrets_client():
    """Get the Secrets Manager client (lazy initialization, reused across Lambda invocations)."""
    global _client
    if _client is None:
        _client = boto3.client("secretsmanager")
    return _client
