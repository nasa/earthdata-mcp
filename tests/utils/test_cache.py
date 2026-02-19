"""Tests for cache utility."""

import json
import os
from unittest.mock import Mock, patch

import pytest
import redis

from util.cache import RedisCache, get_redis_credentials


@pytest.fixture
def mock_redis_credentials():
    """Mock Redis credentials from Secrets Manager."""
    return {
        "host": "test-redis.example.com",
        "port": 6379,
        "password": "test-password",
        "ssl": True,
    }


class TestGetRedisCredentials:
    """Test get_redis_credentials function."""

    @patch("util.cache.REDIS_SECRET_ID", None)
    def test_raises_error_without_secret_id(self):
        """Should raise RuntimeError when REDIS_SECRET_ID is not set."""
        # Clear the lru_cache to ensure fresh state
        get_redis_credentials.cache_clear()

        with pytest.raises(RuntimeError) as exc_info:
            get_redis_credentials()

        assert "REDIS_SECRET_ID environment variable is not set" in str(exc_info.value)

    @patch("util.cache.REDIS_SECRET_ID", "test-secret-arn")
    @patch("util.cache.get_secrets_client")
    def test_fetches_credentials_from_secrets_manager(self, mock_get_client):
        """Should fetch credentials from Secrets Manager."""
        get_redis_credentials.cache_clear()

        mock_client = Mock()
        mock_get_client.return_value = mock_client
        mock_client.get_secret_value.return_value = {
            "SecretString": json.dumps(
                {
                    "host": "redis.example.com",
                    "port": 6379,
                    "password": "secret-password",
                    "ssl": True,
                }
            )
        }

        result = get_redis_credentials()

        mock_client.get_secret_value.assert_called_once_with(SecretId="test-secret-arn")
        assert result["host"] == "redis.example.com"
        assert result["password"] == "secret-password"


class TestRedisCacheInitialization:
    """Test RedisCache initialization and connection."""

    @patch.dict(os.environ, {"REDIS_HOST": ""}, clear=False)
    @patch("util.cache.REDIS_SECRET_ID", "test-secret-arn")
    @patch("util.cache.get_redis_credentials")
    @patch("util.cache.redis.Redis")
    def test_successful_initialization(
        self, mock_redis_class, mock_get_creds, mock_redis_credentials
    ):
        """Test successful Redis connection during initialization."""
        mock_get_creds.return_value = mock_redis_credentials
        mock_client = Mock()
        mock_redis_class.return_value = mock_client
        mock_client.ping.return_value = True

        with patch("util.cache.logger") as mock_logger:
            client = RedisCache()

            # Verify Redis client was created with correct parameters
            mock_redis_class.assert_called_once_with(
                host="test-redis.example.com",
                port=6379,
                password="test-password",
                ssl=True,
                ssl_cert_reqs=None,
                socket_connect_timeout=2,
                socket_timeout=2,
            )

            # Verify connection test was performed
            mock_client.ping.assert_called_once()

            # Verify success was logged (should have 2 info calls)
            assert mock_logger.info.call_count == 2
            assert (
                mock_logger.info.call_args_list[0][0][0]
                == "Using AWS Secrets Manager Redis configuration"
            )
            assert (
                mock_logger.info.call_args_list[1][0][0]
                == "Successfully connected to Redis via Secrets Manager"
            )

            # Verify client is available
            assert client.client is not None

    @patch.dict(os.environ, {"REDIS_HOST": ""}, clear=False)
    @patch("util.cache.REDIS_SECRET_ID", "test-secret-arn")
    @patch("util.cache.get_redis_credentials")
    @patch("util.cache.redis.Redis")
    def test_connection_failure_during_init(
        self, mock_redis_class, mock_get_creds, mock_redis_credentials
    ):
        """Test handling of connection failure during initialization."""
        mock_get_creds.return_value = mock_redis_credentials
        mock_client = Mock()
        mock_redis_class.return_value = mock_client
        mock_client.ping.side_effect = redis.ConnectionError("Connection refused")

        with patch("util.cache.logger") as mock_logger:
            client = RedisCache()

            # Verify warning was logged
            mock_logger.warning.assert_called_once()
            assert "Failed to connect to Redis" in mock_logger.warning.call_args[0][0]

            # Verify client is None
            assert client.client is None

    @patch.dict(os.environ, {"REDIS_HOST": ""}, clear=False)
    @patch("util.cache.REDIS_SECRET_ID", "test-secret-arn")
    @patch("util.cache.get_redis_credentials")
    @patch("util.cache.redis.Redis")
    def test_redis_creation_failure(self, mock_redis_class, mock_get_creds, mock_redis_credentials):
        """Test handling when Redis client creation fails."""
        mock_get_creds.return_value = mock_redis_credentials
        mock_redis_class.side_effect = Exception("Redis creation failed")

        with patch("util.cache.logger") as mock_logger:
            cache = RedisCache()

            # Verify warning was logged
            mock_logger.warning.assert_called_once()
            assert "Failed to connect to Redis" in mock_logger.warning.call_args[0][0]

            # Verify client is None
            assert cache.client is None

    @patch.dict(os.environ, {"REDIS_HOST": ""}, clear=False)
    @patch("util.cache.REDIS_SECRET_ID", None)
    def test_no_connection_without_secret_id(self):
        """Test that Redis is disabled when REDIS_SECRET_ID is not set."""
        with patch("util.cache.logger") as mock_logger:
            client = RedisCache()

            mock_logger.info.assert_called_once_with(
                "REDIS_SECRET_ID not set and no local Redis config found, caching disabled"
            )
            assert client.client is None

    def test_local_redis_successful_connection(self, monkeypatch):
        """Test successful connection to local Redis using REDIS_HOST."""
        monkeypatch.setenv("REDIS_HOST", "localhost")

        mock_client = Mock()
        mock_redis_class = Mock(return_value=mock_client)
        monkeypatch.setattr("util.cache.redis.Redis", mock_redis_class)

        mock_client.ping.return_value = True

        mock_logger = Mock()
        monkeypatch.setattr("util.cache.logger", mock_logger)

        client = RedisCache()

        mock_redis_class.assert_called_once_with(
            host="localhost",
            port=6379,  # Default port
            password=None,
            ssl=False,  # Local development doesn't use SSL
            socket_connect_timeout=2,
            socket_timeout=2,
        )

        mock_client.ping.assert_called_once()

        assert mock_logger.info.call_count == 2
        assert (
            mock_logger.info.call_args_list[0][0][0]
            == "Using local Redis configuration (REDIS_HOST)"
        )
        assert "Successfully connected to local Redis" in mock_logger.info.call_args_list[1][0][0]

        assert client.client is not None

    def test_local_redis_with_custom_port_and_password(self, monkeypatch):
        """Test local Redis connection with custom port and password."""
        monkeypatch.setenv("REDIS_HOST", "localhost")
        monkeypatch.setenv("REDIS_PORT", "6380")
        monkeypatch.setenv("REDIS_PASSWORD", "dev-pass")

        mock_client = Mock()
        mock_redis_class = Mock(return_value=mock_client)
        monkeypatch.setattr("util.cache.redis.Redis", mock_redis_class)

        mock_client.ping.return_value = True

        client = RedisCache()

        mock_redis_class.assert_called_once_with(
            host="localhost",
            port=6380,
            password="dev-pass",  # noqa: S106 - Suppress linting warning, not a real password
            ssl=False,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        assert client.client is not None

    def test_local_redis_takes_precedence_over_secrets(self, monkeypatch, mock_redis_credentials):
        """Test that REDIS_HOST takes precedence over REDIS_SECRET_ID."""
        monkeypatch.setenv("REDIS_HOST", "localhost")
        monkeypatch.setattr("util.cache.REDIS_SECRET_ID", "test-secret-arn")

        mock_get_creds = Mock(return_value=mock_redis_credentials)
        monkeypatch.setattr("util.cache.get_redis_credentials", mock_get_creds)

        mock_client = Mock()
        mock_redis_class = Mock(return_value=mock_client)
        monkeypatch.setattr("util.cache.redis.Redis", mock_redis_class)

        mock_client.ping.return_value = True

        mock_logger = Mock()
        monkeypatch.setattr("util.cache.logger", mock_logger)

        RedisCache()

        # Verify local Redis was used (not Secrets Manager)
        assert "Using local Redis configuration" in mock_logger.info.call_args_list[0][0][0]
        mock_redis_class.assert_called_once_with(
            host="localhost",
            port=6379,
            password=None,
            ssl=False,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        # Secrets Manager should not have been called
        mock_get_creds.assert_not_called()

    def test_local_redis_connection_failure(self, monkeypatch):
        """Test graceful handling of local Redis connection failure."""
        monkeypatch.setenv("REDIS_HOST", "localhost")

        mock_client = Mock()
        mock_redis_class = Mock(return_value=mock_client)
        monkeypatch.setattr("util.cache.redis.Redis", mock_redis_class)

        mock_client.ping.side_effect = redis.ConnectionError("Connection refused")

        mock_logger = Mock()
        monkeypatch.setattr("util.cache.logger", mock_logger)

        client = RedisCache()

        mock_logger.warning.assert_called_once()
        assert "Failed to connect to local Redis" in mock_logger.warning.call_args[0][0]

        assert client.client is None

    def test_local_redis_creation_failure(self, monkeypatch):
        """Test graceful handling when the Redis constructor raises with REDIS_HOST set."""
        monkeypatch.setenv("REDIS_HOST", "localhost")

        mock_redis_class = Mock(side_effect=Exception("Redis creation failed"))
        monkeypatch.setattr("util.cache.redis.Redis", mock_redis_class)

        mock_logger = Mock()
        monkeypatch.setattr("util.cache.logger", mock_logger)

        client = RedisCache()

        mock_logger.warning.assert_called_once()
        assert "Failed to connect to local Redis" in mock_logger.warning.call_args[0][0]

        assert client.client is None


class TestIsAvailable:
    """Test the is_available method."""

    @patch.dict(os.environ, {"REDIS_HOST": ""}, clear=False)
    @patch("util.cache.REDIS_SECRET_ID", None)
    def test_is_available_with_no_client(self):
        """Test is_available when client is None."""
        client = RedisCache()

        assert client.is_available() is False

    @patch.dict(os.environ, {"REDIS_HOST": ""}, clear=False)
    @patch("util.cache.REDIS_SECRET_ID", "test-secret-arn")
    @patch("util.cache.get_redis_credentials")
    @patch("util.cache.redis.Redis")
    def test_is_available_with_working_client(
        self, mock_redis_class, mock_get_creds, mock_redis_credentials
    ):
        """Test is_available when client works."""
        mock_get_creds.return_value = mock_redis_credentials
        mock_client = Mock()
        mock_redis_class.return_value = mock_client
        mock_client.ping.return_value = True

        client = RedisCache()

        # Call is_available (which will call ping again)
        assert client.is_available() is True

        # Verify ping was called at least twice (once in init, once in is_available)
        assert mock_client.ping.call_count >= 2

    @patch.dict(os.environ, {"REDIS_HOST": ""}, clear=False)
    @patch("util.cache.REDIS_SECRET_ID", "test-secret-arn")
    @patch("util.cache.get_redis_credentials")
    @patch("util.cache.redis.Redis")
    def test_is_available_with_connection_error(
        self, mock_redis_class, mock_get_creds, mock_redis_credentials
    ):
        """Test is_available when ping fails."""
        mock_get_creds.return_value = mock_redis_credentials
        mock_client = Mock()
        mock_redis_class.return_value = mock_client

        # First ping succeeds (for init), second fails (for is_available)
        mock_client.ping.side_effect = [True, redis.ConnectionError("Connection lost")]

        client = RedisCache()

        # Now is_available should return False
        assert client.is_available() is False


class TestGetMethod:
    """Test the get method."""

    @patch.dict(os.environ, {"REDIS_HOST": ""}, clear=False)
    @patch("util.cache.REDIS_SECRET_ID", None)
    def test_get_with_unavailable_client(self):
        """Test get when client is unavailable."""
        client = RedisCache()

        result = client.get("test_key")

        assert result is None

    @patch.dict(os.environ, {"REDIS_HOST": ""}, clear=False)
    @patch("util.cache.REDIS_SECRET_ID", "test-secret-arn")
    @patch("util.cache.get_redis_credentials")
    @patch("util.cache.redis.Redis")
    def test_get_successful_retrieval(
        self, mock_redis_class, mock_get_creds, mock_redis_credentials
    ):
        """Test successful data retrieval from cache."""
        mock_get_creds.return_value = mock_redis_credentials
        mock_client = Mock()
        mock_redis_class.return_value = mock_client

        # Setup test data
        test_data = {"key": "value", "number": 42}
        mock_client.get.return_value = json.dumps(test_data)

        client = RedisCache()
        result = client.get("test_key")

        assert result == test_data
        mock_client.get.assert_called_with("test_key")

    @patch.dict(os.environ, {"REDIS_HOST": ""}, clear=False)
    @patch("util.cache.REDIS_SECRET_ID", "test-secret-arn")
    @patch("util.cache.get_redis_credentials")
    @patch("util.cache.redis.Redis")
    def test_get_key_not_found(self, mock_redis_class, mock_get_creds, mock_redis_credentials):
        """Test get when key doesn't exist."""
        mock_get_creds.return_value = mock_redis_credentials
        mock_client = Mock()
        mock_redis_class.return_value = mock_client
        mock_client.get.return_value = None

        client = RedisCache()
        result = client.get("nonexistent_key")

        assert result is None
        mock_client.get.assert_called_with("nonexistent_key")

    @patch.dict(os.environ, {"REDIS_HOST": ""}, clear=False)
    @patch("util.cache.REDIS_SECRET_ID", "test-secret-arn")
    @patch("util.cache.get_redis_credentials")
    @patch("util.cache.redis.Redis")
    def test_get_with_redis_error(self, mock_redis_class, mock_get_creds, mock_redis_credentials):
        """Test get with Redis error."""
        mock_get_creds.return_value = mock_redis_credentials
        mock_client = Mock()
        mock_redis_class.return_value = mock_client
        mock_client.get.side_effect = redis.RedisError("Server error")

        client = RedisCache()

        with patch("util.cache.logger") as mock_logger:
            result = client.get("test_key")

            assert result is None
            mock_logger.warning.assert_called_once()
            assert "Cache read error" in mock_logger.warning.call_args[0][0]


class TestSetMethod:
    """Test the set method."""

    @patch.dict(os.environ, {"REDIS_HOST": ""}, clear=False)
    @patch("util.cache.REDIS_SECRET_ID", None)
    def test_set_with_unavailable_client(self):
        """Test set when client is unavailable."""
        client = RedisCache()

        result = client.set("test_key", {"data": "value"})

        assert result is False

    @patch.dict(os.environ, {"REDIS_HOST": ""}, clear=False)
    @patch("util.cache.REDIS_SECRET_ID", "test-secret-arn")
    @patch("util.cache.get_redis_credentials")
    @patch("util.cache.redis.Redis")
    def test_set_successful(self, mock_redis_class, mock_get_creds, mock_redis_credentials):
        """Test successful data storage in cache."""
        mock_get_creds.return_value = mock_redis_credentials
        mock_client = Mock()
        mock_redis_class.return_value = mock_client

        client = RedisCache()
        test_data = {"key": "value", "number": 42}

        result = client.set("test_key", test_data, 600)

        assert result is True
        mock_client.setex.assert_called_once_with("test_key", 600, json.dumps(test_data))

    @patch.dict(os.environ, {"REDIS_HOST": ""}, clear=False)
    @patch("util.cache.REDIS_SECRET_ID", "test-secret-arn")
    @patch("util.cache.get_redis_credentials")
    @patch("util.cache.redis.Redis")
    def test_set_with_default_ttl(self, mock_redis_class, mock_get_creds, mock_redis_credentials):
        """Test set with default TTL."""
        mock_get_creds.return_value = mock_redis_credentials
        mock_client = Mock()
        mock_redis_class.return_value = mock_client

        client = RedisCache()
        test_data = {"key": "value"}

        result = client.set("test_key", test_data)

        assert result is True
        mock_client.setex.assert_called_once_with("test_key", 900, json.dumps(test_data))

    @patch.dict(os.environ, {"REDIS_HOST": ""}, clear=False)
    @patch("util.cache.REDIS_SECRET_ID", "test-secret-arn")
    @patch("util.cache.get_redis_credentials")
    @patch("util.cache.redis.Redis")
    def test_set_with_redis_error(self, mock_redis_class, mock_get_creds, mock_redis_credentials):
        """Test set with Redis error."""
        mock_get_creds.return_value = mock_redis_credentials
        mock_client = Mock()
        mock_redis_class.return_value = mock_client
        mock_client.setex.side_effect = redis.RedisError("Server error")

        client = RedisCache()

        with patch("util.cache.logger") as mock_logger:
            result = client.set("test_key", {"data": "value"})

            assert result is False
            mock_logger.warning.assert_called_once()
            assert "Cache write error" in mock_logger.warning.call_args[0][0]


class TestHgetMethod:
    """Test the hget method."""

    @patch.dict(os.environ, {"REDIS_HOST": ""}, clear=False)
    @patch("util.cache.REDIS_SECRET_ID", None)
    def test_hget_with_unavailable_client(self):
        """Test hget when client is unavailable."""
        client = RedisCache()

        result = client.hget("test_hash", "field")

        assert result is None

    @patch.dict(os.environ, {"REDIS_HOST": ""}, clear=False)
    @patch("util.cache.REDIS_SECRET_ID", "test-secret-arn")
    @patch("util.cache.get_redis_credentials")
    @patch("util.cache.redis.Redis")
    def test_hget_successful_retrieval(
        self, mock_redis_class, mock_get_creds, mock_redis_credentials
    ):
        """Test successful data retrieval from hash."""
        mock_get_creds.return_value = mock_redis_credentials
        mock_client = Mock()
        mock_redis_class.return_value = mock_client

        test_data = {"uuid": "abc-123", "term": "MODIS"}
        mock_client.hget.return_value = json.dumps(test_data)

        client = RedisCache()
        result = client.hget("kms:scheme:instruments", "MODIS")

        assert result == test_data
        mock_client.hget.assert_called_with("kms:scheme:instruments", "MODIS")

    @patch.dict(os.environ, {"REDIS_HOST": ""}, clear=False)
    @patch("util.cache.REDIS_SECRET_ID", "test-secret-arn")
    @patch("util.cache.get_redis_credentials")
    @patch("util.cache.redis.Redis")
    def test_hget_field_not_found(self, mock_redis_class, mock_get_creds, mock_redis_credentials):
        """Test hget when field doesn't exist."""
        mock_get_creds.return_value = mock_redis_credentials
        mock_client = Mock()
        mock_redis_class.return_value = mock_client
        mock_client.hget.return_value = None

        client = RedisCache()
        result = client.hget("kms:scheme:instruments", "NONEXISTENT")

        assert result is None

    @patch.dict(os.environ, {"REDIS_HOST": ""}, clear=False)
    @patch("util.cache.REDIS_SECRET_ID", "test-secret-arn")
    @patch("util.cache.get_redis_credentials")
    @patch("util.cache.redis.Redis")
    def test_hget_with_redis_error(self, mock_redis_class, mock_get_creds, mock_redis_credentials):
        """Test hget with Redis error."""
        mock_get_creds.return_value = mock_redis_credentials
        mock_client = Mock()
        mock_redis_class.return_value = mock_client
        mock_client.hget.side_effect = redis.RedisError("Server error")

        client = RedisCache()

        with patch("util.cache.logger") as mock_logger:
            result = client.hget("test_hash", "field")

            assert result is None
            mock_logger.warning.assert_called_once()
            assert "Hash read error" in mock_logger.warning.call_args[0][0]


class TestHmgetMethod:
    """Test the hmget method."""

    @patch.dict(os.environ, {"REDIS_HOST": ""}, clear=False)
    @patch("util.cache.REDIS_SECRET_ID", None)
    def test_hmget_with_unavailable_client(self):
        """Test hmget when client is unavailable."""
        client = RedisCache()

        result = client.hmget("test_hash", ["field1", "field2"])

        assert result == {"field1": None, "field2": None}

    @patch.dict(os.environ, {"REDIS_HOST": ""}, clear=False)
    @patch("util.cache.REDIS_SECRET_ID", "test-secret-arn")
    @patch("util.cache.get_redis_credentials")
    @patch("util.cache.redis.Redis")
    def test_hmget_successful_retrieval(
        self, mock_redis_class, mock_get_creds, mock_redis_credentials
    ):
        """Test successful batch retrieval from hash."""
        mock_get_creds.return_value = mock_redis_credentials
        mock_client = Mock()
        mock_redis_class.return_value = mock_client

        data1 = {"uuid": "uuid-1", "term": "MODIS"}
        data2 = {"uuid": "uuid-2", "term": "ASTER"}
        mock_client.hmget.return_value = [json.dumps(data1), json.dumps(data2)]

        client = RedisCache()
        result = client.hmget("kms:scheme:instruments", ["MODIS", "ASTER"])

        assert result == {"MODIS": data1, "ASTER": data2}
        mock_client.hmget.assert_called_with("kms:scheme:instruments", ["MODIS", "ASTER"])

    @patch.dict(os.environ, {"REDIS_HOST": ""}, clear=False)
    @patch("util.cache.REDIS_SECRET_ID", "test-secret-arn")
    @patch("util.cache.get_redis_credentials")
    @patch("util.cache.redis.Redis")
    def test_hmget_partial_results(self, mock_redis_class, mock_get_creds, mock_redis_credentials):
        """Test hmget with some fields not found."""
        mock_get_creds.return_value = mock_redis_credentials
        mock_client = Mock()
        mock_redis_class.return_value = mock_client

        data1 = {"uuid": "uuid-1", "term": "MODIS"}
        mock_client.hmget.return_value = [json.dumps(data1), None]

        client = RedisCache()
        result = client.hmget("kms:scheme:instruments", ["MODIS", "MISSING"])

        assert result["MODIS"] == data1
        assert result["MISSING"] is None

    @patch.dict(os.environ, {"REDIS_HOST": ""}, clear=False)
    @patch("util.cache.REDIS_SECRET_ID", "test-secret-arn")
    @patch("util.cache.get_redis_credentials")
    @patch("util.cache.redis.Redis")
    def test_hmget_with_redis_error(self, mock_redis_class, mock_get_creds, mock_redis_credentials):
        """Test hmget with Redis error."""
        mock_get_creds.return_value = mock_redis_credentials
        mock_client = Mock()
        mock_redis_class.return_value = mock_client
        mock_client.hmget.side_effect = redis.RedisError("Server error")

        client = RedisCache()

        with patch("util.cache.logger") as mock_logger:
            result = client.hmget("test_hash", ["field1", "field2"])

            assert result == {"field1": None, "field2": None}
            mock_logger.warning.assert_called_once()
            assert "Hash multi-read error" in mock_logger.warning.call_args[0][0]


class TestHmsetMethod:
    """Test the hmset method."""

    @patch.dict(os.environ, {"REDIS_HOST": ""}, clear=False)
    @patch("util.cache.REDIS_SECRET_ID", None)
    def test_hmset_with_unavailable_client(self):
        """Test hmset when client is unavailable."""
        client = RedisCache()

        result = client.hmset("test_hash", {"field": {"data": "value"}})

        assert result is False

    @patch.dict(os.environ, {"REDIS_HOST": ""}, clear=False)
    @patch("util.cache.REDIS_SECRET_ID", "test-secret-arn")
    @patch("util.cache.get_redis_credentials")
    @patch("util.cache.redis.Redis")
    def test_hmset_successful(self, mock_redis_class, mock_get_creds, mock_redis_credentials):
        """Test successful batch storage in hash."""
        mock_get_creds.return_value = mock_redis_credentials
        mock_client = Mock()
        mock_redis_class.return_value = mock_client

        client = RedisCache()
        data = {
            "MODIS": {"uuid": "uuid-1", "term": "MODIS"},
            "ASTER": {"uuid": "uuid-2", "term": "ASTER"},
        }

        result = client.hmset("kms:scheme:instruments", data, 86400)

        assert result is True
        # Verify hset was called with serialized data
        call_args = mock_client.hset.call_args
        assert call_args[0][0] == "kms:scheme:instruments"
        mapping = call_args[1]["mapping"]
        assert json.loads(mapping["MODIS"]) == data["MODIS"]
        assert json.loads(mapping["ASTER"]) == data["ASTER"]
        # Verify TTL was set
        mock_client.expire.assert_called_once_with("kms:scheme:instruments", 86400)

    @patch.dict(os.environ, {"REDIS_HOST": ""}, clear=False)
    @patch("util.cache.REDIS_SECRET_ID", "test-secret-arn")
    @patch("util.cache.get_redis_credentials")
    @patch("util.cache.redis.Redis")
    def test_hmset_with_empty_mapping(
        self, mock_redis_class, mock_get_creds, mock_redis_credentials
    ):
        """Test hmset with empty mapping."""
        mock_get_creds.return_value = mock_redis_credentials
        mock_client = Mock()
        mock_redis_class.return_value = mock_client

        client = RedisCache()
        result = client.hmset("test_hash", {})

        assert result is True
        mock_client.hset.assert_not_called()

    @patch.dict(os.environ, {"REDIS_HOST": ""}, clear=False)
    @patch("util.cache.REDIS_SECRET_ID", "test-secret-arn")
    @patch("util.cache.get_redis_credentials")
    @patch("util.cache.redis.Redis")
    def test_hmset_with_redis_error(self, mock_redis_class, mock_get_creds, mock_redis_credentials):
        """Test hmset with Redis error."""
        mock_get_creds.return_value = mock_redis_credentials
        mock_client = Mock()
        mock_redis_class.return_value = mock_client
        mock_client.hset.side_effect = redis.RedisError("Server error")

        client = RedisCache()

        with patch("util.cache.logger") as mock_logger:
            result = client.hmset("test_hash", {"field": {"data": "value"}})

            assert result is False
            mock_logger.warning.assert_called_once()
            assert "Hash write error" in mock_logger.warning.call_args[0][0]


class TestHexistsMethod:
    """Test the hexists method."""

    @patch.dict(os.environ, {"REDIS_HOST": ""}, clear=False)
    @patch("util.cache.REDIS_SECRET_ID", None)
    def test_hexists_with_unavailable_client(self):
        """Test hexists when client is unavailable."""
        client = RedisCache()

        result = client.hexists("test_hash")

        assert result is False

    @patch.dict(os.environ, {"REDIS_HOST": ""}, clear=False)
    @patch("util.cache.REDIS_SECRET_ID", "test-secret-arn")
    @patch("util.cache.get_redis_credentials")
    @patch("util.cache.redis.Redis")
    def test_hexists_when_key_exists(
        self, mock_redis_class, mock_get_creds, mock_redis_credentials
    ):
        """Test hexists when key exists."""
        mock_get_creds.return_value = mock_redis_credentials
        mock_client = Mock()
        mock_redis_class.return_value = mock_client
        mock_client.exists.return_value = 1

        client = RedisCache()
        result = client.hexists("kms:scheme:instruments")

        assert result is True
        mock_client.exists.assert_called_with("kms:scheme:instruments")

    @patch.dict(os.environ, {"REDIS_HOST": ""}, clear=False)
    @patch("util.cache.REDIS_SECRET_ID", "test-secret-arn")
    @patch("util.cache.get_redis_credentials")
    @patch("util.cache.redis.Redis")
    def test_hexists_when_key_does_not_exist(
        self, mock_redis_class, mock_get_creds, mock_redis_credentials
    ):
        """Test hexists when key does not exist."""
        mock_get_creds.return_value = mock_redis_credentials
        mock_client = Mock()
        mock_redis_class.return_value = mock_client
        mock_client.exists.return_value = 0

        client = RedisCache()
        result = client.hexists("nonexistent_hash")

        assert result is False

    @patch.dict(os.environ, {"REDIS_HOST": ""}, clear=False)
    @patch("util.cache.REDIS_SECRET_ID", "test-secret-arn")
    @patch("util.cache.get_redis_credentials")
    @patch("util.cache.redis.Redis")
    def test_hexists_with_redis_error(
        self, mock_redis_class, mock_get_creds, mock_redis_credentials
    ):
        """Test hexists with Redis error."""
        mock_get_creds.return_value = mock_redis_credentials
        mock_client = Mock()
        mock_redis_class.return_value = mock_client
        mock_client.exists.side_effect = redis.RedisError("Server error")

        client = RedisCache()

        with patch("util.cache.logger") as mock_logger:
            result = client.hexists("test_hash")

            assert result is False
            mock_logger.warning.assert_called_once()
            assert "Hash exists check error" in mock_logger.warning.call_args[0][0]
