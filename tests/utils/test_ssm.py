"""Tests for util.ssm."""

from unittest.mock import MagicMock, patch

import pytest

from util.ssm import get_parameter, get_ssm_client


def test_get_ssm_client_lazy_init():
    """Test function."""
    import util.ssm

    util.ssm._client = None

    with patch("boto3.client") as mock_boto:
        mock_client = MagicMock()
        mock_boto.return_value = mock_client

        client1 = get_ssm_client()
        assert client1 is mock_client
        mock_boto.assert_called_once_with("ssm")

        client2 = get_ssm_client()
        assert client2 is mock_client
        mock_boto.assert_called_once()


def test_get_parameter():
    """Test function."""
    import util.ssm

    util.ssm.get_parameter.cache_clear()
    with patch("util.ssm.get_ssm_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.get_parameter.return_value = {"Parameter": {"Value": "test_val"}}

        val = get_parameter("test_key")
        assert val == "test_val"
        mock_client.get_parameter.assert_called_once_with(Name="test_key", WithDecryption=True)


def test_get_parameter_not_found():
    """Test function."""
    import botocore.exceptions

    import util.ssm

    util.ssm.get_parameter.cache_clear()
    with patch("util.ssm.get_ssm_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        error_response = {"Error": {"Code": "ParameterNotFound"}}
        mock_client.get_parameter.side_effect = botocore.exceptions.ClientError(
            error_response, "GetParameter"
        )

        with pytest.raises(botocore.exceptions.ClientError):
            get_parameter("missing_key")
