"""Pytest fixtures for lambda handler tests."""

import pytest

from util.sqs import _clear_client


@pytest.fixture(autouse=True)
def clear_sqs_client():
    """Clear the cached SQS client before each test."""
    _clear_client()
    yield
    _clear_client()
