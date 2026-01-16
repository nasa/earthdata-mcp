"""Database utilities for PostgreSQL with pgvector support."""

import json
import logging
import os
from functools import lru_cache
from typing import Any

import psycopg
from pgvector.psycopg import register_vector

from util.secrets import get_secrets_client

logger = logging.getLogger(__name__)

DATABASE_SECRET_ID = os.environ.get("DATABASE_SECRET_ID")

_connection = None


@lru_cache(maxsize=1)
def get_database_credentials() -> dict[str, Any]:
    """Fetch database credentials from Secrets Manager (cached)."""
    client = get_secrets_client()
    response = client.get_secret_value(SecretId=DATABASE_SECRET_ID)
    return json.loads(response["SecretString"])


def get_db_connection() -> psycopg.Connection:
    """
    Get the database connection (lazy initialization, reused across Lambda invocations).

    The connection is cached at module level for reuse during warm starts.
    If the connection is closed or broken, a new one will be created.
    """
    global _connection
    if _connection is None or _connection.closed:
        creds = get_database_credentials()
        _connection = psycopg.connect(creds["url"])
        register_vector(_connection)
    return _connection
