"""
Abstract Database Connection Interface

This module defines the abstract base class for database connections.
"""

from abc import ABC, abstractmethod


class AbstractDBConnection(ABC):  # pylint: disable=unnecessary-pass
    """Abstract base class for database connections."""

    @abstractmethod
    def create_db_instance(self, region, **kwargs):
        """Create a new database instance."""
        pass

    @abstractmethod
    def connect(self):
        """Establish connection to the database."""
        pass

    @abstractmethod
    def search(self, query_params: dict):
        """
        Perform a combined search using keywords, spatial and temporal.
        """
        pass

    @abstractmethod
    def close(self):
        """Close the database connection."""
        pass

    @abstractmethod
    def set_connection_parameters(self, params):
        """Sets the database connection parameters."""
        pass

    @abstractmethod
    def _setup_db(self):
        """Sets up the initial database state."""
        pass

    @abstractmethod
    def insert_embeddings(self, data):
        """Insert data into a specified table."""
        pass

    @abstractmethod
    def delete_embedding(self, concept_id):
        """Delete data from a specified table"""
        pass
