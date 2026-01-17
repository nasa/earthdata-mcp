"""AWS Bedrock client utility."""

import os

import boto3

_clients: dict[str, object] = {}

BEDROCK_REGION = os.environ.get("BEDROCK_REGION", "us-east-1")


def get_bedrock_client(region: str | None = None):
    """Get the Bedrock runtime client (lazy initialization, reused per-region across Lambda invocations)."""
    effective_region = region or BEDROCK_REGION
    if effective_region not in _clients:
        _clients[effective_region] = boto3.client("bedrock-runtime", region_name=effective_region)
    return _clients[effective_region]
