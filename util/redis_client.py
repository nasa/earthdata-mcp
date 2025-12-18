"""Redis client for caching operation"""

import os
import json
import logging
from typing import Any, Dict, Optional
import redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


class CacheClient:
    """
    Redis-based cache client with error handling and configuration management.

    Provides a consistent interface for caching operations across all tools.
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
                port=6379,
                password=os.getenv("REDIS_PASSWORD"),
                ssl=True,
                ssl_cert_reqs=None,
            )

            # Test connection
            self.client.ping()
            logger.info("Successfully connected to Redis")

        except Exception as e:
            logger.warning(
                "Failed to connect to Redis: %s. Caching will be disabled.", e
            )
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

    def get(self, key: str) -> Optional[Dict[str, Any]]:
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

    def set(self, key: str, value: Dict[str, Any], ttl: int = 900) -> bool:
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
