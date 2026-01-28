"""Datastore abstractions for embedding storage."""

from util.datastores.base import EmbeddingDatastore
from util.datastores.postgres import PostgresEmbeddingDatastore

# Module-level singleton (lazy initialized)
_datastore: EmbeddingDatastore | None = None


def get_datastore() -> EmbeddingDatastore:
    """Get or create the shared datastore singleton.

    Returns the same datastore instance across all callers,
    avoiding repeated database connection overhead.
    """
    global _datastore  # pylint: disable=global-statement
    if _datastore is None:
        _datastore = PostgresEmbeddingDatastore()
    return _datastore


def reset_datastore() -> None:
    """Reset the datastore singleton (primarily for testing)."""
    global _datastore  # pylint: disable=global-statement
    if _datastore is not None:
        _datastore.close()
    _datastore = None


__all__ = [
    "EmbeddingDatastore",
    "PostgresEmbeddingDatastore",
    "get_datastore",
    "reset_datastore",
]
