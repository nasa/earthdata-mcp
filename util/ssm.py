"""AWS SSM Parameter Store client utility."""

from functools import lru_cache

import boto3

_client = None


def get_ssm_client():
    """Get the SSM client (lazy initialization, reused across Lambda invocations)."""
    global _client
    if _client is None:
        _client = boto3.client("ssm")
    return _client


@lru_cache(maxsize=32)
def get_parameter(name: str) -> str:
    """
    Fetch a parameter value from SSM Parameter Store (cached).

    Args:
        name: The parameter name.

    Returns:
        The parameter value (decrypted if SecureString).

    Raises:
        botocore.exceptions.ClientError: If parameter not found or access denied.
    """
    client = get_ssm_client()
    response = client.get_parameter(Name=name, WithDecryption=True)
    return response["Parameter"]["Value"]
