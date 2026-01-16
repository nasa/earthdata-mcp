"""Datastore abstractions for embedding storage."""

import os
from typing import TYPE_CHECKING

from util.datastores.base import EmbeddingDatastore
from util.datastores.postgres import PostgresEmbeddingDatastore

if TYPE_CHECKING:
    pass

# Datastore backend configuration
DATASTORE_BACKEND = os.environ.get("DATASTORE_BACKEND", "postgres")


def get_datastore() -> EmbeddingDatastore:
    """
    Factory function to get the configured datastore implementation.

    Configure via DATASTORE_BACKEND environment variable:
    - "postgres" (default): PostgreSQL with pgvector

    Returns:
        An EmbeddingDatastore implementation.

    Raises:
        ValueError: If the configured backend is not supported.
    """
    if DATASTORE_BACKEND == "postgres":
        return PostgresEmbeddingDatastore()
    else:
        raise ValueError(f"Unsupported datastore backend: {DATASTORE_BACKEND}")


__all__ = [
    "EmbeddingDatastore",
    "PostgresEmbeddingDatastore",
    "get_datastore",
]
