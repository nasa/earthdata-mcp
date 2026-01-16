"""Cache client abstractions for caching operations."""

import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Any

import redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


class CacheClient(ABC):
    """
    Abstract base class for cache clients.

    Provides a consistent interface for caching operations across all tools.
    Implementations can use different backends (Redis, Memcached, etc.).
    """

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the cache client is available and connected."""

    @abstractmethod
    def get(self, key: str) -> dict[str, Any] | None:
        """
        Get a value from cache.

        Args:
            key: Cache key to retrieve

        Returns:
            Parsed data if found, None if not found or on error
        """

    @abstractmethod
    def set(self, key: str, value: dict[str, Any], ttl: int = 900) -> bool:
        """
        Set a value in cache.

        Args:
            key: Cache key
            value: Data to cache
            ttl: Time to live in seconds (default: 15 minutes)

        Returns:
            True if successful, False otherwise
        """


class RedisCache(CacheClient):
    """
    Redis-based cache client implementation.

    Provides caching operations using Redis with error handling
    and configuration management.
    """

    def __init__(self):
        """Initialize Redis client with environment-based configuration."""
        self.client = None
        self._connect()

    def _connect(self):
        """Establish Redis connection with proper error handling."""
        try:
            self.client = redis.Redis(
                host=os.getenv("REDIS_HOST", "localhost"),
                port=int(os.getenv("REDIS_PORT", "6379")),
                password=os.getenv("REDIS_PASSWORD"),
                ssl=os.getenv("REDIS_SSL", "true").lower() == "true",
                ssl_cert_reqs=None,
                socket_connect_timeout=2,
                socket_timeout=2,
            )

            # Test connection
            self.client.ping()
            logger.info("Successfully connected to Redis")

        except Exception as e:
            logger.warning("Failed to connect to Redis: %s. Caching will be disabled.", e)
            self.client = None

    def is_available(self) -> bool:
        """Check if Redis client is available and connected."""
        if self.client is None:
            return False

        try:
            self.client.ping()
            return True
        except RedisError:
            return False

    def get(self, key: str) -> dict[str, Any] | None:
        """
        Get a value from Redis cache.

        Args:
            key: Cache key to retrieve

        Returns:
            Parsed JSON data if found, None if not found or on error
        """
        if not self.is_available():
            return None

        try:
            cached_data = self.client.get(key)
            if cached_data:
                return json.loads(cached_data)
            return None

        except (RedisError, json.JSONDecodeError, TypeError) as e:
            logger.warning("Cache read error for key '%s': %s", key, e)
            return None

    def set(self, key: str, value: dict[str, Any], ttl: int = 900) -> bool:
        """
        Set a value in Redis cache.

        Args:
            key: Cache key
            value: Data to cache (will be JSON serialized)
            ttl: Time to live in seconds (default: 15 minutes)

        Returns:
            True if successful, False otherwise
        """
        if not self.is_available():
            return False

        try:
            serialized_data = json.dumps(value)
            self.client.setex(key, ttl, serialized_data)
            return True

        except (RedisError, TypeError, ValueError) as e:
            logger.warning("Cache write error for key '%s': %s", key, e)
            return False


_cache_client = None


def get_cache_client() -> CacheClient:
    """
    Get the cache client (lazy initialization, reused across Lambda invocations).

    Returns:
        A RedisCache instance.
    """
    global _cache_client
    if _cache_client is None:
        _cache_client = RedisCache()
    return _cache_client


__all__ = [
    "CacheClient",
    "RedisCache",
    "get_cache_client",
]
