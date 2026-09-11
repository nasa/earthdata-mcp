"""Tests for the util.harmony.client module."""

import importlib
import types
from unittest.mock import MagicMock, patch

import pytest
import harmony


def _load_module() -> types.ModuleType:
    """Load the client module dynamically."""
    return importlib.import_module("util.harmony.client")


# ---------------------------------------------------------
# Tests for harmony_environment()
# ---------------------------------------------------------

def test_harmony_environment_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the environment defaults to PROD when HARMONY_ENV is missing."""
    monkeypatch.delenv("HARMONY_ENV", raising=False)
    module = _load_module()
    
    assert module.harmony_environment() == harmony.Environment.PROD


@pytest.mark.parametrize(
    "env_string,expected_enum",
    [
        ("prod", harmony.Environment.PROD),
        ("PROD", harmony.Environment.PROD),
        (" uat ", harmony.Environment.UAT),
        ("sit", harmony.Environment.SIT),
        ("local", harmony.Environment.LOCAL),
    ],
)
def test_harmony_environment_valid_mappings(
    monkeypatch: pytest.MonkeyPatch, env_string: str, expected_enum: harmony.Environment
) -> None:
    """Test that valid HARMONY_ENV strings map to the correct enum."""
    monkeypatch.setenv("HARMONY_ENV", env_string)
    module = _load_module()
    
    assert module.harmony_environment() == expected_enum


def test_harmony_environment_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that an invalid HARMONY_ENV string raises a ValueError."""
    monkeypatch.setenv("HARMONY_ENV", "dev")
    module = _load_module()
    
    with pytest.raises(ValueError, match="Invalid HARMONY_ENV 'dev'"):
        module.harmony_environment()


# ---------------------------------------------------------
# Tests for get_client()
# ---------------------------------------------------------

@pytest.fixture(autouse=True)
def clear_client_cache() -> None:
    """Automatically clear the LRU cache before each test."""
    module = _load_module()
    module.get_client.cache_clear()


@patch("util.harmony.client.harmony.Client")
@patch("util.harmony.client.harmony_environment")
def test_get_client_with_token(
    mock_env: MagicMock, mock_client_class: MagicMock
) -> None:
    """Test that get_client builds a Harmony Client using a token and the current env."""
    module = _load_module()
    
    mock_env.return_value = harmony.Environment.UAT
    mock_client_instance = MagicMock()
    mock_client_class.return_value = mock_client_instance
    
    # Act
    client = module.get_client("fake-token-123")
    
    # Assert
    assert client == mock_client_instance
    mock_client_class.assert_called_once_with(
        env=harmony.Environment.UAT, 
        token="fake-token-123"
    )


@pytest.mark.parametrize("invalid_token", [None, "", False])
def test_get_client_without_token_raises_error(invalid_token) -> None:
    """Test that get_client raises a ValueError if token is missing or empty."""
    module = _load_module()
    
    with pytest.raises(ValueError, match="A valid token is required"):
        module.get_client(invalid_token)


@patch("util.harmony.client.harmony.Client")
def test_get_client_caching(mock_client_class: MagicMock) -> None:
    """Test that get_client utilizes lru_cache properly and only initializes once."""
    module = _load_module()
    
    # Call multiple times with the same token
    client1 = module.get_client("cached-token")
    client2 = module.get_client("cached-token")
    
    # Assert Client was only constructed once
    assert client1 is client2
    mock_client_class.assert_called_once()
