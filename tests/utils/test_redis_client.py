"""Tests for Redis client utility."""

import json
from unittest.mock import Mock, patch
import redis

from util.redis_client import CacheClient


class TestCacheClientInitialization:
    """Test CacheClient initialization and connection."""

    @patch("util.redis_client.redis.Redis")
    def test_successful_initialization(self, mock_redis_class):
        """Test successful Redis connection during initialization."""
        mock_client = Mock()
        mock_redis_class.return_value = mock_client
        mock_client.ping.return_value = True

        with patch("util.redis_client.logger") as mock_logger:
            client = CacheClient()

            # Verify Redis client was created with correct parameters
            mock_redis_class.assert_called_once_with(
                host="localhost",  # Default value
                port=6379,  # Default value
                password=None,  # Default value
                ssl=True,
                ssl_cert_reqs=None,
            )

            # Verify connection test was performed
            mock_client.ping.assert_called_once()

            # Verify success was logged
            mock_logger.info.assert_called_once_with("Successfully connected to Redis")

            # Verify client is available
            assert client.client is not None

    @patch("util.redis_client.redis.Redis")
    def test_connection_failure_during_init(self, mock_redis_class):
        """Test handling of connection failure during initialization."""
        mock_client = Mock()
        mock_redis_class.return_value = mock_client
        mock_client.ping.side_effect = redis.ConnectionError("Connection refused")

        with patch("util.redis_client.logger") as mock_logger:
            client = CacheClient()

            # Verify warning was logged
            mock_logger.warning.assert_called_once()
            assert "Failed to connect to Redis" in mock_logger.warning.call_args[0][0]

            # Verify client is None
            assert client.client is None

    @patch("util.redis_client.redis.Redis")
    def test_redis_creation_failure(self, mock_redis_class):
        """Test handling when Redis client creation fails."""
        mock_redis_class.side_effect = Exception("Redis creation failed")

        with patch("util.redis_client.logger") as mock_logger:
            client = CacheClient()

            # Verify warning was logged
            mock_logger.warning.assert_called_once()
            assert "Failed to connect to Redis" in mock_logger.warning.call_args[0][0]

            # Verify client is None
            assert client.client is None


class TestIsAvailable:
    """Test the is_available method."""

    def test_is_available_with_no_client(self):
        """Test is_available when client is None."""
        client = CacheClient()
        client.client = None

        assert client.is_available() is False

    @patch("util.redis_client.redis.Redis")
    def test_is_available_with_working_client(self, mock_redis_class):
        """Test is_available when client works."""
        mock_client = Mock()
        mock_redis_class.return_value = mock_client
        mock_client.ping.return_value = True

        client = CacheClient()

        # Call is_available (which will call ping again)
        assert client.is_available() is True

        # Verify ping was called at least twice (once in init, once in is_available)
        assert mock_client.ping.call_count >= 2

    @patch("util.redis_client.redis.Redis")
    def test_is_available_with_connection_error(self, mock_redis_class):
        """Test is_available when ping fails."""
        mock_client = Mock()
        mock_redis_class.return_value = mock_client

        # First ping succeeds (for init), second fails (for is_available)
        mock_client.ping.side_effect = [True, redis.ConnectionError("Connection lost")]

        client = CacheClient()

        # Now is_available should return False
        assert client.is_available() is False


class TestGetMethod:
    """Test the get method."""

    def test_get_with_unavailable_client(self):
        """Test get when client is unavailable."""
        client = CacheClient()
        client.client = None

        result = client.get("test_key")

        assert result is None

    @patch("util.redis_client.redis.Redis")
    def test_get_successful_retrieval(self, mock_redis_class):
        """Test successful data retrieval from cache."""
        mock_client = Mock()
        mock_redis_class.return_value = mock_client

        # Setup test data
        test_data = {"key": "value", "number": 42}
        mock_client.get.return_value = json.dumps(test_data)

        client = CacheClient()
        result = client.get("test_key")

        assert result == test_data
        mock_client.get.assert_called_with("test_key")

    @patch("util.redis_client.redis.Redis")
    def test_get_key_not_found(self, mock_redis_class):
        """Test get when key doesn't exist."""
        mock_client = Mock()
        mock_redis_class.return_value = mock_client
        mock_client.get.return_value = None

        client = CacheClient()
        result = client.get("nonexistent_key")

        assert result is None
        mock_client.get.assert_called_with("nonexistent_key")

    @patch("util.redis_client.redis.Redis")
    def test_get_with_redis_error(self, mock_redis_class):
        """Test get with Redis error."""
        mock_client = Mock()
        mock_redis_class.return_value = mock_client
        mock_client.get.side_effect = redis.RedisError("Server error")

        client = CacheClient()

        with patch("util.redis_client.logger") as mock_logger:
            result = client.get("test_key")

            assert result is None
            mock_logger.warning.assert_called_once()
            assert "Cache read error" in mock_logger.warning.call_args[0][0]


class TestSetMethod:
    """Test the set method."""

    def test_set_with_unavailable_client(self):
        """Test set when client is unavailable."""
        client = CacheClient()
        client.client = None

        result = client.set("test_key", {"data": "value"})

        assert result is False

    @patch("util.redis_client.redis.Redis")
    def test_set_successful(self, mock_redis_class):
        """Test successful data storage in cache."""
        mock_client = Mock()
        mock_redis_class.return_value = mock_client

        client = CacheClient()
        test_data = {"key": "value", "number": 42}

        result = client.set("test_key", test_data, 600)

        assert result is True
        mock_client.setex.assert_called_once_with(
            "test_key", 600, json.dumps(test_data)
        )

    @patch("util.redis_client.redis.Redis")
    def test_set_with_default_ttl(self, mock_redis_class):
        """Test set with default TTL."""
        mock_client = Mock()
        mock_redis_class.return_value = mock_client

        client = CacheClient()
        test_data = {"key": "value"}

        result = client.set("test_key", test_data)

        assert result is True
        mock_client.setex.assert_called_once_with(
            "test_key", 900, json.dumps(test_data)
        )

    @patch("util.redis_client.redis.Redis")
    def test_set_with_redis_error(self, mock_redis_class):
        """Test set with Redis error."""
        mock_client = Mock()
        mock_redis_class.return_value = mock_client
        mock_client.setex.side_effect = redis.RedisError("Server error")

        client = CacheClient()

        with patch("util.redis_client.logger") as mock_logger:
            result = client.set("test_key", {"data": "value"})

            assert result is False
            mock_logger.warning.assert_called_once()
            assert "Cache write error" in mock_logger.warning.call_args[0][0]
