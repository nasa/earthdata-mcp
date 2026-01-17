"""Tests for cache utility."""

import json
import os
from unittest.mock import Mock, patch

import redis

from util.cache import RedisCache


class TestRedisCacheInitialization:
    """Test RedisCache initialization and connection."""

    @patch.dict(os.environ, {"REDIS_HOST": "localhost"}, clear=True)
    @patch("util.cache.redis.Redis")
    def test_successful_initialization(self, mock_redis_class):
        """Test successful Redis connection during initialization."""
        mock_client = Mock()
        mock_redis_class.return_value = mock_client
        mock_client.ping.return_value = True

        with patch("util.cache.logger") as mock_logger:
            client = RedisCache()

            # Verify Redis client was created with correct parameters
            mock_redis_class.assert_called_once_with(
                host="localhost",  # Default value
                port=6379,  # Default value
                password=None,  # Default value
                ssl=True,
                ssl_cert_reqs=None,
                socket_connect_timeout=2,
                socket_timeout=2,
            )

            # Verify connection test was performed
            mock_client.ping.assert_called_once()

            # Verify success was logged
            mock_logger.info.assert_called_once_with("Successfully connected to Redis")

            # Verify client is available
            assert client.client is not None

    @patch.dict(os.environ, {}, clear=True)
    @patch("util.cache.redis.Redis")
    def test_connection_failure_during_init(self, mock_redis_class):
        """Test handling of connection failure during initialization."""
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

    @patch.dict(os.environ, {}, clear=True)
    @patch("util.cache.redis.Redis")
    def test_redis_creation_failure(self, mock_redis_class):
        """Test handling when Redis client creation fails."""
        mock_redis_class.side_effect = Exception("Redis creation failed")

        with patch("util.cache.logger") as mock_logger:
            client = RedisCache()

            # Verify warning was logged
            mock_logger.warning.assert_called_once()
            assert "Failed to connect to Redis" in mock_logger.warning.call_args[0][0]

            # Verify client is None
            assert client.client is None


class TestIsAvailable:
    """Test the is_available method."""

    @patch.dict(os.environ, {}, clear=True)
    @patch("util.cache.redis.Redis")
    def test_is_available_with_no_client(self, mock_redis_class):
        """Test is_available when client is None."""
        mock_redis_class.side_effect = Exception("Connection failed")
        client = RedisCache()

        assert client.is_available() is False

    @patch.dict(os.environ, {}, clear=True)
    @patch("util.cache.redis.Redis")
    def test_is_available_with_working_client(self, mock_redis_class):
        """Test is_available when client works."""
        mock_client = Mock()
        mock_redis_class.return_value = mock_client
        mock_client.ping.return_value = True

        client = RedisCache()

        # Call is_available (which will call ping again)
        assert client.is_available() is True

        # Verify ping was called at least twice (once in init, once in is_available)
        assert mock_client.ping.call_count >= 2

    @patch.dict(os.environ, {}, clear=True)
    @patch("util.cache.redis.Redis")
    def test_is_available_with_connection_error(self, mock_redis_class):
        """Test is_available when ping fails."""
        mock_client = Mock()
        mock_redis_class.return_value = mock_client

        # First ping succeeds (for init), second fails (for is_available)
        mock_client.ping.side_effect = [True, redis.ConnectionError("Connection lost")]

        client = RedisCache()

        # Now is_available should return False
        assert client.is_available() is False


class TestGetMethod:
    """Test the get method."""

    @patch.dict(os.environ, {}, clear=True)
    @patch("util.cache.redis.Redis")
    def test_get_with_unavailable_client(self, mock_redis_class):
        """Test get when client is unavailable."""
        mock_redis_class.side_effect = Exception("Connection failed")
        client = RedisCache()

        result = client.get("test_key")

        assert result is None

    @patch.dict(os.environ, {}, clear=True)
    @patch("util.cache.redis.Redis")
    def test_get_successful_retrieval(self, mock_redis_class):
        """Test successful data retrieval from cache."""
        mock_client = Mock()
        mock_redis_class.return_value = mock_client

        # Setup test data
        test_data = {"key": "value", "number": 42}
        mock_client.get.return_value = json.dumps(test_data)

        client = RedisCache()
        result = client.get("test_key")

        assert result == test_data
        mock_client.get.assert_called_with("test_key")

    @patch.dict(os.environ, {}, clear=True)
    @patch("util.cache.redis.Redis")
    def test_get_key_not_found(self, mock_redis_class):
        """Test get when key doesn't exist."""
        mock_client = Mock()
        mock_redis_class.return_value = mock_client
        mock_client.get.return_value = None

        client = RedisCache()
        result = client.get("nonexistent_key")

        assert result is None
        mock_client.get.assert_called_with("nonexistent_key")

    @patch.dict(os.environ, {}, clear=True)
    @patch("util.cache.redis.Redis")
    def test_get_with_redis_error(self, mock_redis_class):
        """Test get with Redis error."""
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

    @patch.dict(os.environ, {}, clear=True)
    @patch("util.cache.redis.Redis")
    def test_set_with_unavailable_client(self, mock_redis_class):
        """Test set when client is unavailable."""
        mock_redis_class.side_effect = Exception("Connection failed")
        client = RedisCache()

        result = client.set("test_key", {"data": "value"})

        assert result is False

    @patch.dict(os.environ, {}, clear=True)
    @patch("util.cache.redis.Redis")
    def test_set_successful(self, mock_redis_class):
        """Test successful data storage in cache."""
        mock_client = Mock()
        mock_redis_class.return_value = mock_client

        client = RedisCache()
        test_data = {"key": "value", "number": 42}

        result = client.set("test_key", test_data, 600)

        assert result is True
        mock_client.setex.assert_called_once_with("test_key", 600, json.dumps(test_data))

    @patch.dict(os.environ, {}, clear=True)
    @patch("util.cache.redis.Redis")
    def test_set_with_default_ttl(self, mock_redis_class):
        """Test set with default TTL."""
        mock_client = Mock()
        mock_redis_class.return_value = mock_client

        client = RedisCache()
        test_data = {"key": "value"}

        result = client.set("test_key", test_data)

        assert result is True
        mock_client.setex.assert_called_once_with("test_key", 900, json.dumps(test_data))

    @patch.dict(os.environ, {}, clear=True)
    @patch("util.cache.redis.Redis")
    def test_set_with_redis_error(self, mock_redis_class):
        """Test set with Redis error."""
        mock_client = Mock()
        mock_redis_class.return_value = mock_client
        mock_client.setex.side_effect = redis.RedisError("Server error")

        client = RedisCache()

        with patch("util.cache.logger") as mock_logger:
            result = client.set("test_key", {"data": "value"})

            assert result is False
            mock_logger.warning.assert_called_once()
            assert "Cache write error" in mock_logger.warning.call_args[0][0]
