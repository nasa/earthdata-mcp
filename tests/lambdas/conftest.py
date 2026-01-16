"""Pytest fixtures for lambda handler tests."""

import pytest


@pytest.fixture(autouse=True)
def clear_sqs_client():
    """Clear the cached SQS client before each test."""
    from util.sqs import _clear_client

    _clear_client()
    yield
    _clear_client()
