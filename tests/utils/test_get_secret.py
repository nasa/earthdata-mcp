"""Tests for get_secret module"""

import json
from unittest.mock import patch, Mock

import pytest  # pylint: disable=import-error
from botocore.exceptions import ClientError  # pylint: disable=import-error

from util.get_secret import get_secret  # pylint: disable=import-error


class TestGetSecret:
    """Tests for get_secret function"""

    @patch("util.get_secret.boto3.session.Session")
    def test_get_secret_success(self, mock_session):
        """Test successful secret retrieval"""
        mock_client = Mock()
        mock_session.return_value.client.return_value = mock_client

        secret_value = {"username": "test_user", "password": "test_pass"}
        mock_client.get_secret_value.return_value = {
            "SecretString": json.dumps(secret_value)
        }

        result = get_secret("my-secret")

        assert result == secret_value
        mock_client.get_secret_value.assert_called_once_with(SecretId="my-secret")

    @patch("util.get_secret.boto3.session.Session")
    def test_get_secret_with_complex_json(self, mock_session):
        """Test secret retrieval with complex JSON structure"""
        mock_client = Mock()
        mock_session.return_value.client.return_value = mock_client

        secret_value = {
            "database": {
                "host": "localhost",
                "port": 5432,
                "credentials": {"username": "admin", "password": "secret123"},
            },
            "api_keys": ["key1", "key2", "key3"],
        }
        mock_client.get_secret_value.return_value = {
            "SecretString": json.dumps(secret_value)
        }

        result = get_secret("complex-secret")

        assert result == secret_value
        assert result["database"]["credentials"]["username"] == "admin"
        assert len(result["api_keys"]) == 3

    @patch("util.get_secret.boto3.session.Session")
    def test_get_secret_client_error_resource_not_found(self, mock_session):
        """Test handling of ResourceNotFoundException"""
        mock_client = Mock()
        mock_session.return_value.client.return_value = mock_client

        error = ClientError(
            {
                "Error": {
                    "Code": "ResourceNotFoundException",
                    "Message": "Secret not found",
                }
            },
            "GetSecretValue",
        )
        mock_client.get_secret_value.side_effect = error

        with pytest.raises(ClientError) as exc_info:
            get_secret("non-existent-secret")

        assert exc_info.value.response["Error"]["Code"] == "ResourceNotFoundException"

    @patch("util.get_secret.boto3.session.Session")
    def test_get_secret_client_error_access_denied(self, mock_session):
        """Test handling of AccessDeniedException"""
        mock_client = Mock()
        mock_session.return_value.client.return_value = mock_client

        error = ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "Access denied"}},
            "GetSecretValue",
        )
        mock_client.get_secret_value.side_effect = error

        with pytest.raises(ClientError) as exc_info:
            get_secret("restricted-secret")

        assert exc_info.value.response["Error"]["Code"] == "AccessDeniedException"

    @patch("util.get_secret.boto3.session.Session")
    def test_get_secret_client_error_invalid_request(self, mock_session):
        """Test handling of InvalidRequestException"""
        mock_client = Mock()
        mock_session.return_value.client.return_value = mock_client

        error = ClientError(
            {
                "Error": {
                    "Code": "InvalidRequestException",
                    "Message": "Invalid request",
                }
            },
            "GetSecretValue",
        )
        mock_client.get_secret_value.side_effect = error

        with pytest.raises(ClientError) as exc_info:
            get_secret("my-secret")

        assert exc_info.value.response["Error"]["Code"] == "InvalidRequestException"

    @patch("util.get_secret.boto3.session.Session")
    def test_get_secret_with_arn(self, mock_session):
        """Test secret retrieval using ARN"""
        mock_client = Mock()
        mock_session.return_value.client.return_value = mock_client

        secret_value = {"key": "value"}
        mock_client.get_secret_value.return_value = {
            "SecretString": json.dumps(secret_value)
        }

        secret_arn = (
            "arn:aws:secretsmanager:us-east-1:123456789012:secret:my-secret-ABC123"
        )
        result = get_secret(secret_arn)

        assert result == secret_value
        mock_client.get_secret_value.assert_called_once_with(SecretId=secret_arn)

    @patch("util.get_secret.boto3.session.Session")
    def test_get_secret_creates_session_and_client(self, mock_session):
        """Test that boto3 session and client are created correctly"""
        mock_session_instance = Mock()
        mock_client = Mock()
        mock_session.return_value = mock_session_instance
        mock_session_instance.client.return_value = mock_client

        mock_client.get_secret_value.return_value = {
            "SecretString": json.dumps({"key": "value"})
        }

        get_secret("test-secret")

        mock_session.assert_called_once()
        mock_session_instance.client.assert_called_once_with(
            service_name="secretsmanager"
        )

    @patch("util.get_secret.boto3.session.Session")
    def test_get_secret_with_empty_string(self, mock_session):
        """Test secret retrieval with empty JSON object"""
        mock_client = Mock()
        mock_session.return_value.client.return_value = mock_client

        mock_client.get_secret_value.return_value = {"SecretString": "{}"}

        result = get_secret("empty-secret")

        assert result == {}
