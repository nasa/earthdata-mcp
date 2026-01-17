"""SQS client utility."""

import boto3

_client = None


def get_sqs_client():
    """Get the SQS client (lazy initialization, reused across Lambda invocations)."""
    global _client
    if _client is None:
        _client = boto3.client("sqs")
    return _client


def _clear_client():
    """Clear the cached client (for testing only)."""
    global _client
    _client = None
