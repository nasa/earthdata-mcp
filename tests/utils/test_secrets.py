"""Tests for util.secrets."""

from unittest.mock import MagicMock, patch

from util.secrets import get_secrets_client


def test_get_secrets_client_lazy_init():
    """Test function."""
    # Clear any existing client singleton
    import util.secrets

    util.secrets._client = None

    with patch("boto3.client") as mock_boto:
        mock_client = MagicMock()
        mock_boto.return_value = mock_client

        # First call initializes client
        client1 = get_secrets_client()
        assert client1 is mock_client
        mock_boto.assert_called_once_with("secretsmanager")

        # Second call uses singleton, doesn't call boto3 again
        client2 = get_secrets_client()
        assert client2 is mock_client
        mock_boto.assert_called_once()
