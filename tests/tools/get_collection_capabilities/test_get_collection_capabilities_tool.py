"""Tests for the get_collection_capabilities MCP tool."""

import importlib
import types
from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest


MOCK_CAPABILITIES_RESPONSE = {
    "conceptId": "C1234567-PROV",
    "shortName": "SHORTNAME",
    "summary": {
        "subsetting": {
            "bbox": False,
            "dimension": False,
            "shape": False,
            "temporal": False,
            "variable": False
        },
        "reprojection": {
            "supported": False,
            "supportedProjections": [],
            "interpolationMethods": []
        },
        "averaging": {
            "time": False,
            "area": False
        },
        "concatenation": False,
        "outputFormats": []
    },
    "services": [],
    "variables": [],
    "capabilitiesVersion": "3"
}


def _load_tool() -> types.ModuleType:
    """Load the tool module dynamically to avoid circular imports."""
    return importlib.import_module("tools.get_collection_capabilities.tool")


@pytest.fixture
def mock_get_access_token() -> Generator[MagicMock, None, None]:
    """Mock the get_access_token function specifically within the tool module."""
    with patch("tools.get_collection_capabilities.tool.get_access_token") as mock_token_func:
        # Create a mock object that has a `.token` attribute
        mock_token_obj = MagicMock()
        mock_token_obj.token = "fake-jwt-token"
        mock_token_func.return_value = mock_token_obj
        yield mock_token_func


@pytest.fixture
def mock_get_client() -> Generator[MagicMock, None, None]:
    """Mock util.harmony.client.get_client within the tool."""
    with patch("tools.get_collection_capabilities.tool.get_client") as mock_client:
        yield mock_client


@pytest.fixture
def mock_capabilities_request() -> Generator[MagicMock, None, None]:
    """Mock harmony.CapabilitiesRequest within the tool."""
    with patch("tools.get_collection_capabilities.tool.harmony.CapabilitiesRequest") as mock_req:
        yield mock_req


def test_get_collection_capabilities_concept_id_success(
    mock_get_client: MagicMock, 
    mock_capabilities_request: MagicMock,
    mock_get_access_token: MagicMock
) -> None:
    """Test successful capability retrieval using a collection concept ID."""
    tool = _load_tool()

    # Arrange mocks
    mock_client_instance = MagicMock()
    mock_get_client.return_value = mock_client_instance
    mock_client_instance.submit.return_value = MOCK_CAPABILITIES_RESPONSE

    mock_req_instance = MagicMock()
    mock_capabilities_request.return_value = mock_req_instance

    # Act
    result = tool.get_collection_capabilities(
        collection_concept_id="C1234567-PROV"
    )

    # Assert
    assert result == MOCK_CAPABILITIES_RESPONSE
    
    # Verify the token function was called and passed to get_client
    mock_get_access_token.assert_called_once()
    mock_get_client.assert_called_once_with("fake-jwt-token")
    mock_capabilities_request.assert_called_once_with(collection_id="C1234567-PROV")
    mock_client_instance.submit.assert_called_once_with(mock_req_instance)


def test_get_collection_capabilities_short_name_success(
    mock_get_client: MagicMock, 
    mock_capabilities_request: MagicMock,
    mock_get_access_token: MagicMock
) -> None:
    """Test successful capability retrieval using a collection short name."""
    tool = _load_tool()

    # Arrange mocks
    mock_client_instance = MagicMock()
    mock_get_client.return_value = mock_client_instance
    mock_client_instance.submit.return_value = MOCK_CAPABILITIES_RESPONSE

    mock_req_instance = MagicMock()
    mock_capabilities_request.return_value = mock_req_instance

    # Act
    result = tool.get_collection_capabilities(
        short_name="SHORTNAME"
    )

    # Assert
    assert result == MOCK_CAPABILITIES_RESPONSE
    mock_get_access_token.assert_called_once()
    mock_get_client.assert_called_once_with("fake-jwt-token")
    mock_capabilities_request.assert_called_once_with(short_name="SHORTNAME")
    mock_client_instance.submit.assert_called_once_with(mock_req_instance)


def test_get_collection_capabilities_calls_trace_update(
    mock_get_client: MagicMock, 
    mock_capabilities_request: MagicMock,
    mock_get_access_token: MagicMock
) -> None:
    """Test telemetry tracing is called correctly."""
    tool = _load_tool()
    
    mock_get_client.return_value.submit.return_value = {}

    with patch.object(tool, "trace_update") as mock_trace_update:
        tool.get_collection_capabilities(
            short_name="MODIS",
        )

    assert mock_trace_update.called


def test_get_collection_capabilities_validation_error_missing_both() -> None:
    """Test that providing neither ID nor short_name returns the gracefully handled error output."""
    tool = _load_tool()

    # Act
    result = tool.get_collection_capabilities(
        collection_concept_id=None,
        short_name=None,
    )

    # Assert
    assert result.get("code") in ["ValueError", "ValidationError"]
    assert "Must specify either collection_id or short_name" in result.get("description", "")


def test_get_collection_capabilities_validation_error_provides_both() -> None:
    """Test that providing both ID and short_name returns the gracefully handled error output."""
    tool = _load_tool()

    # Act
    result = tool.get_collection_capabilities(
        collection_concept_id="C1234567-PROV",
        short_name="MOD09GQ",
    )

    # Assert
    assert result.get("code") in ["ValueError", "ValidationError"]
    assert "Must specify only one of collection_id or short_name, not both" in result.get("description", "")


def test_get_collection_capabilities_client_error(
    mock_get_client: MagicMock, 
    mock_capabilities_request: MagicMock,
    mock_get_access_token: MagicMock
) -> None:
    """Test behavior when the Harmony client raises an exception."""
    tool = _load_tool()

    mock_client_instance = MagicMock()
    mock_get_client.return_value = mock_client_instance
    
    # Simulate an error from the Harmony API
    mock_client_instance.submit.side_effect = Exception("Upstream Harmony error")

    # Act
    result = tool.get_collection_capabilities(
        short_name="ERROR_CASE"
    )
    
    # Assert
    assert result.get("code") == "Exception"
    assert "Failed to fetch capabilities from Harmony: Upstream Harmony error" in result.get("description", "")
