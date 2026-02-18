"""Cache client abstractions for caching operations."""

import json
import logging
import os
from abc import ABC, abstractmethod
from functools import lru_cache
from typing import Any

import redis
from redis.exceptions import RedisError

from util.secrets import get_secrets_client

logger = logging.getLogger(__name__)

REDIS_SECRET_ID = os.environ.get("REDIS_SECRET_ID")


@lru_cache(maxsize=1)
def get_redis_credentials() -> dict[str, Any]:
    """
    Fetch Redis credentials from Secrets Manager (cached).

    Returns:
        Dict with host, port, password, ssl keys.

    Raises:
        RuntimeError: If REDIS_SECRET_ID is not set.
    """
    if not REDIS_SECRET_ID:
        raise RuntimeError(
            "REDIS_SECRET_ID environment variable is not set. "
            "Set this to your AWS Secrets Manager secret ID containing Redis credentials."
        )
    client = get_secrets_client()
    response = client.get_secret_value(SecretId=REDIS_SECRET_ID)
    return json.loads(response["SecretString"])


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

    @abstractmethod
    def hget(self, key: str, field: str) -> dict[str, Any] | None:
        """
        Get a single field from a hash.

        Args:
            key: Hash key
            field: Field name within the hash

        Returns:
            Parsed data if found, None if not found or on error
        """

    @abstractmethod
    def hmget(self, key: str, fields: list[str]) -> dict[str, dict[str, Any] | None]:
        """
        Get multiple fields from a hash.

        Args:
            key: Hash key
            fields: List of field names to retrieve

        Returns:
            Dict mapping field names to their values (None if field not found)
        """

    @abstractmethod
    def hmset(self, key: str, mapping: dict[str, dict[str, Any]], ttl: int = 86400) -> bool:
        """
        Set multiple fields in a hash.

        Args:
            key: Hash key
            mapping: Dict of field names to values
            ttl: Time to live in seconds (default: 24 hours)

        Returns:
            True if successful, False otherwise
        """

    @abstractmethod
    def hexists(self, key: str) -> bool:
        """
        Check if a hash key exists in cache.

        Args:
            key: Hash key to check

        Returns:
            True if exists, False otherwise
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
        # Try local development configuration first
        redis_host = os.environ.get("REDIS_HOST")
        redis_password = os.environ.get("REDIS_PASSWORD")
        redis_port = os.environ.get("REDIS_PORT", "6379")

        if redis_host:
            # Local development mode - use direct environment variables
            try:
                logger.info("Using local Redis configuration (REDIS_HOST)")
                self.client = redis.Redis(
                    host=redis_host,
                    port=int(redis_port),
                    password=redis_password if redis_password else None,
                    ssl=False,  # Local development typically doesn't use SSL
                    socket_connect_timeout=2,
                    socket_timeout=2,
                )
                self.client.ping()
                logger.info(
                    "Successfully connected to local Redis at %s:%s", redis_host, redis_port
                )
                return
            except Exception as e:
                logger.warning("Failed to connect to local Redis: %s", e)
                self.client = None
                return

        # Production mode - use AWS Secrets Manager
        if not REDIS_SECRET_ID:
            logger.info("REDIS_SECRET_ID not set and no local Redis config found, caching disabled")
            self.client = None
            return

        try:
            creds = get_redis_credentials()
            logger.info("Using AWS Secrets Manager Redis configuration")
            self.client = redis.Redis(
                host=creds["host"],
                port=int(creds["port"]),
                password=creds["password"],
                ssl=creds.get("ssl", True),
                ssl_cert_reqs=None,
                socket_connect_timeout=2,
                socket_timeout=2,
            )

            # Test connection
            self.client.ping()
            logger.info("Successfully connected to Redis via Secrets Manager")

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

    def hget(self, key: str, field: str) -> dict[str, Any] | None:
        """
        Get a single field from a Redis hash.

        Args:
            key: Hash key
            field: Field name within the hash

        Returns:
            Parsed JSON data if found, None if not found or on error
        """
        if not self.is_available():
            return None

        try:
            cached_data = self.client.hget(key, field)
            if cached_data:
                return json.loads(cached_data)
            return None

        except (RedisError, json.JSONDecodeError, TypeError) as e:
            logger.warning("Hash read error for key '%s' field '%s': %s", key, field, e)
            return None

    def hmget(self, key: str, fields: list[str]) -> dict[str, dict[str, Any] | None]:
        """
        Get multiple fields from a Redis hash.

        Args:
            key: Hash key
            fields: List of field names to retrieve

        Returns:
            Dict mapping field names to their values (None if field not found)
        """
        if not self.is_available():
            return dict.fromkeys(fields)

        try:
            values = self.client.hmget(key, fields)
            result = {}
            for field, value in zip(fields, values, strict=True):
                if value:
                    result[field] = json.loads(value)
                else:
                    result[field] = None
            return result

        except (RedisError, json.JSONDecodeError, TypeError) as e:
            logger.warning("Hash multi-read error for key '%s': %s", key, e)
            return dict.fromkeys(fields)

    def hmset(self, key: str, mapping: dict[str, dict[str, Any]], ttl: int = 86400) -> bool:
        """
        Set multiple fields in a Redis hash.

        Args:
            key: Hash key
            mapping: Dict of field names to values (will be JSON serialized)
            ttl: Time to live in seconds (default: 24 hours)

        Returns:
            True if successful, False otherwise
        """
        if not self.is_available():
            return False

        if not mapping:
            return True

        try:
            serialized = {field: json.dumps(value) for field, value in mapping.items()}
            self.client.hset(key, mapping=serialized)
            self.client.expire(key, ttl)
            return True

        except (RedisError, TypeError, ValueError) as e:
            logger.warning("Hash write error for key '%s': %s", key, e)
            return False

    def hexists(self, key: str) -> bool:
        """
        Check if a hash key exists in Redis.

        Args:
            key: Hash key to check

        Returns:
            True if exists, False otherwise
        """
        if not self.is_available():
            return False

        try:
            return self.client.exists(key) > 0
        except RedisError as e:
            logger.warning("Hash exists check error for key '%s': %s", key, e)
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
