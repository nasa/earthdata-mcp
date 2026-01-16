"""AWS Bedrock client utility."""

import os

import boto3

_client = None

BEDROCK_REGION = os.environ.get("BEDROCK_REGION", "us-east-1")


def get_bedrock_client(region: str | None = None):
    """Get the Bedrock runtime client (lazy initialization, reused across Lambda invocations)."""
    global _client  # pylint: disable=global-statement  # Lambda singleton pattern
    if _client is None:
        _client = boto3.client("bedrock-runtime", region_name=region or BEDROCK_REGION)
    return _client
