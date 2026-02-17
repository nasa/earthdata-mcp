"""Tests for database utility."""

import json
import os
from unittest.mock import Mock, patch

import pytest

from util.database import (
    _get_connection_url,
    _is_connection_healthy,
    get_database_credentials,
    get_db_connection,
)


class TestGetDatabaseCredentials:
    """Test get_database_credentials function."""

    @patch("util.database.DATABASE_SECRET_ID", None)
    def test_raises_error_without_secret_id(self):
        """Should raise RuntimeError when DATABASE_SECRET_ID is not set."""
        # Clear the lru_cache to ensure fresh state
        get_database_credentials.cache_clear()

        with pytest.raises(RuntimeError) as exc_info:
            get_database_credentials()

        assert "DATABASE_SECRET_ID environment variable is not set" in str(exc_info.value)

    @patch("util.database.DATABASE_SECRET_ID", "test-db-secret-arn")
    @patch("util.database.get_secrets_client")
    def test_fetches_credentials_from_secrets_manager(self, mock_get_client):
        """Should fetch credentials from Secrets Manager."""
        get_database_credentials.cache_clear()

        mock_client = Mock()
        mock_get_client.return_value = mock_client
        mock_client.get_secret_value.return_value = {
            "SecretString": json.dumps(
                {
                    "url": "postgresql://user:pass@db.example.com:5432/mydb",
                    "username": "dbuser",
                    "password": "dbpass",
                }
            )
        }

        result = get_database_credentials()

        mock_client.get_secret_value.assert_called_once_with(SecretId="test-db-secret-arn")
        assert result["url"] == "postgresql://user:pass@db.example.com:5432/mydb"
        assert result["username"] == "dbuser"

    @patch("util.database.DATABASE_SECRET_ID", "test-db-secret-arn")
    @patch("util.database.get_secrets_client")
    def test_caches_credentials(self, mock_get_client):
        """Should cache credentials across multiple calls."""
        get_database_credentials.cache_clear()

        mock_client = Mock()
        mock_get_client.return_value = mock_client
        mock_client.get_secret_value.return_value = {
            "SecretString": json.dumps({"url": "postgresql://user:pass@db.example.com:5432/mydb"})
        }

        # Call twice
        result1 = get_database_credentials()
        result2 = get_database_credentials()

        # Should only call Secrets Manager once (cached)
        assert mock_client.get_secret_value.call_count == 1
        assert result1 == result2


class TestGetConnectionUrl:
    """Test _get_connection_url function."""

    @patch.dict(os.environ, {}, clear=True)
    @patch("util.database.DATABASE_SECRET_ID", "test-secret")
    @patch("util.database.get_secrets_client")
    def test_returns_url_without_override(self, mock_get_client):
        """Should return URL as-is when DB_HOST is not set."""
        get_database_credentials.cache_clear()

        mock_client = Mock()
        mock_get_client.return_value = mock_client
        mock_client.get_secret_value.return_value = {
            "SecretString": json.dumps(
                {"url": "postgresql://user:pass@prod-db.example.com:5432/mydb"}
            )
        }

        url = _get_connection_url()

        assert url == "postgresql://user:pass@prod-db.example.com:5432/mydb"

    @patch.dict(os.environ, {"DB_HOST": "localhost"}, clear=False)
    @patch("util.database.DATABASE_SECRET_ID", "test-secret")
    @patch("util.database.get_secrets_client")
    def test_overrides_host_with_db_host(self, mock_get_client):
        """Should override hostname when DB_HOST is set."""
        get_database_credentials.cache_clear()

        mock_client = Mock()
        mock_get_client.return_value = mock_client
        mock_client.get_secret_value.return_value = {
            "SecretString": json.dumps(
                {"url": "postgresql://user:pass@prod-db.example.com:5432/mydb"}
            )
        }

        with patch("util.database.logger") as mock_logger:
            url = _get_connection_url()

            assert url == "postgresql://user:pass@localhost:5432/mydb"
            mock_logger.info.assert_called_once_with("Using DB_HOST override: %s", "localhost")

    @patch.dict(os.environ, {"DB_HOST": "127.0.0.1"}, clear=False)
    @patch("util.database.DATABASE_SECRET_ID", "test-secret")
    @patch("util.database.get_secrets_client")
    def test_overrides_host_with_ip_address(self, mock_get_client):
        """Should override hostname with IP address when DB_HOST is set."""
        get_database_credentials.cache_clear()

        mock_client = Mock()
        mock_get_client.return_value = mock_client
        mock_client.get_secret_value.return_value = {
            "SecretString": json.dumps(
                {"url": "postgresql://dbuser:dbpass@rds.amazonaws.com:5432/production"}
            )
        }

        url = _get_connection_url()

        assert url == "postgresql://dbuser:dbpass@127.0.0.1:5432/production"

    @patch.dict(os.environ, {"DB_HOST": "dev-db.local"}, clear=False)
    @patch("util.database.DATABASE_SECRET_ID", "test-secret")
    @patch("util.database.get_secrets_client")
    def test_preserves_port_and_credentials(self, mock_get_client):
        """Should preserve port and credentials when overriding host."""
        get_database_credentials.cache_clear()

        mock_client = Mock()
        mock_get_client.return_value = mock_client
        mock_client.get_secret_value.return_value = {
            "SecretString": json.dumps(
                {"url": "postgresql://myuser:mypassword@original.host:5433/dbname"}
            )
        }

        url = _get_connection_url()

        assert url == "postgresql://myuser:mypassword@dev-db.local:5433/dbname"


class TestIsConnectionHealthy:
    """Test _is_connection_healthy function."""

    def test_returns_false_for_none(self):
        """Should return False when connection is None."""
        assert _is_connection_healthy(None) is False

    def test_returns_false_for_closed_connection(self):
        """Should return False when connection is closed."""
        mock_conn = Mock()
        mock_conn.closed = True

        assert _is_connection_healthy(mock_conn) is False

    def test_returns_true_for_healthy_connection(self):
        """Should return True when connection responds to SELECT 1."""
        mock_conn = Mock()
        mock_conn.closed = False
        mock_transaction = Mock()
        mock_cursor = Mock()

        mock_conn.transaction.return_value.__enter__ = Mock(return_value=mock_transaction)
        mock_conn.transaction.return_value.__exit__ = Mock(return_value=None)
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=None)

        assert _is_connection_healthy(mock_conn) is True
        mock_cursor.execute.assert_called_once_with("SELECT 1")

    def test_returns_false_on_query_exception(self):
        """Should return False when health check query fails."""
        mock_conn = Mock()
        mock_conn.closed = False
        mock_conn.transaction.side_effect = Exception("Connection lost")

        assert _is_connection_healthy(mock_conn) is False


class TestGetDbConnection:
    """Test get_db_connection function."""

    @patch("util.database.DATABASE_SECRET_ID", "test-secret")
    @patch("util.database.get_secrets_client")
    @patch("util.database.psycopg.connect")
    @patch("util.database.register_vector")
    @patch("util.database._connection", None)
    def test_creates_new_connection_when_none_exists(
        self, mock_register, mock_connect, mock_get_client
    ):
        """Should create a new connection when none exists."""
        get_database_credentials.cache_clear()

        mock_client = Mock()
        mock_get_client.return_value = mock_client
        mock_client.get_secret_value.return_value = {
            "SecretString": json.dumps({"url": "postgresql://user:pass@db.example.com:5432/mydb"})
        }

        mock_conn = Mock()
        mock_conn.closed = False
        mock_connect.return_value = mock_conn

        with patch("util.database.logger") as mock_logger:
            conn = get_db_connection()

            mock_connect.assert_called_once_with(
                "postgresql://user:pass@db.example.com:5432/mydb", autocommit=True
            )
            mock_register.assert_called_once_with(mock_conn)
            mock_logger.info.assert_called_once_with("Created new database connection")
            assert conn == mock_conn

    @patch("util.database.DATABASE_SECRET_ID", "test-secret")
    @patch("util.database.get_secrets_client")
    @patch("util.database.psycopg.connect")
    @patch("util.database.register_vector")
    def test_reuses_healthy_connection(self, mock_register, mock_connect, mock_get_client):
        """Should reuse existing healthy connection."""
        get_database_credentials.cache_clear()

        mock_client = Mock()
        mock_get_client.return_value = mock_client
        mock_client.get_secret_value.return_value = {
            "SecretString": json.dumps({"url": "postgresql://user:pass@db.example.com:5432/mydb"})
        }

        # Create a healthy connection
        mock_conn = Mock()
        mock_conn.closed = False
        mock_transaction = Mock()
        mock_cursor = Mock()
        mock_conn.transaction.return_value.__enter__ = Mock(return_value=mock_transaction)
        mock_conn.transaction.return_value.__exit__ = Mock(return_value=None)
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=None)

        with patch("util.database._connection", mock_conn):
            conn = get_db_connection()

            # Should not create a new connection
            mock_connect.assert_not_called()
            assert conn == mock_conn

    @patch("util.database.DATABASE_SECRET_ID", "test-secret")
    @patch("util.database.get_secrets_client")
    @patch("util.database.psycopg.connect")
    @patch("util.database.register_vector")
    def test_recreates_connection_when_unhealthy(
        self, mock_register, mock_connect, mock_get_client
    ):
        """Should create new connection when existing one is unhealthy."""
        get_database_credentials.cache_clear()

        mock_client = Mock()
        mock_get_client.return_value = mock_client
        mock_client.get_secret_value.return_value = {
            "SecretString": json.dumps({"url": "postgresql://user:pass@db.example.com:5432/mydb"})
        }

        # Create an unhealthy (closed) connection
        old_conn = Mock()
        old_conn.closed = True

        # New healthy connection
        new_conn = Mock()
        new_conn.closed = False
        mock_connect.return_value = new_conn

        with patch("util.database._connection", old_conn):
            with patch("util.database.logger") as mock_logger:
                conn = get_db_connection()

                # Should close old connection and create new one
                old_conn.close.assert_called_once()
                mock_connect.assert_called_once()
                mock_register.assert_called_once_with(new_conn)
                mock_logger.info.assert_called_once_with("Created new database connection")
                assert conn == new_conn

    @patch.dict(os.environ, {"DB_HOST": "localhost"}, clear=False)
    @patch("util.database.DATABASE_SECRET_ID", "test-secret")
    @patch("util.database.get_secrets_client")
    @patch("util.database.psycopg.connect")
    @patch("util.database.register_vector")
    @patch("util.database._connection", None)
    def test_uses_db_host_override(self, mock_register, mock_connect, mock_get_client):
        """Should use DB_HOST override when connecting."""
        get_database_credentials.cache_clear()

        mock_client = Mock()
        mock_get_client.return_value = mock_client
        mock_client.get_secret_value.return_value = {
            "SecretString": json.dumps(
                {"url": "postgresql://user:pass@prod-db.example.com:5432/mydb"}
            )
        }

        mock_conn = Mock()
        mock_conn.closed = False
        mock_connect.return_value = mock_conn

        with patch("util.database.logger") as mock_logger:
            conn = get_db_connection()

            # Should connect with localhost instead of prod-db.example.com
            mock_connect.assert_called_once_with(
                "postgresql://user:pass@localhost:5432/mydb", autocommit=True
            )
            # Check that DB_HOST override was logged
            log_messages = [str(call) for call in mock_logger.info.call_args_list]
            assert any("DB_HOST" in msg for msg in log_messages)
            assert conn == mock_conn
