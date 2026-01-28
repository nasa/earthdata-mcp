"""Shared fixtures for discover_data utility tests."""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_instructor_client():
    """Create a mocked instructor client for LLM extraction tests.

    Returns:
        tuple: (mock_instructor, mock_client) where mock_instructor is the
               patched from_provider and mock_client is the client it returns.
    """
    mock_client = MagicMock()
    mock_instructor = MagicMock(return_value=mock_client)
    return mock_instructor, mock_client


@pytest.fixture
def mock_temporal_llm_dependencies(mock_instructor_client):
    """Patch temporal extraction LLM dependencies.

    Yields:
        tuple: (mock_instructor, mock_client, mock_prompt)
    """
    mock_instructor, mock_client = mock_instructor_client
    with (
        patch(
            "tools.discover_data.utils.extract_temporal_constraint.instructor.from_provider",
            mock_instructor,
        ),
        patch(
            "tools.discover_data.utils.extract_temporal_constraint.load_extraction_prompt"
        ) as mock_prompt,
    ):
        mock_prompt.return_value = "System prompt"
        yield mock_instructor, mock_client, mock_prompt


@pytest.fixture
def mock_spatial_llm_dependencies(mock_instructor_client):
    """Patch spatial extraction LLM dependencies.

    Yields:
        tuple: (mock_instructor, mock_client, mock_prompt)
    """
    mock_instructor, mock_client = mock_instructor_client
    with (
        patch(
            "tools.discover_data.utils.extract_spatial_constraint.instructor.from_provider",
            mock_instructor,
        ),
        patch(
            "tools.discover_data.utils.extract_spatial_constraint.load_extraction_prompt"
        ) as mock_prompt,
    ):
        mock_prompt.return_value = "System prompt"
        yield mock_instructor, mock_client, mock_prompt
