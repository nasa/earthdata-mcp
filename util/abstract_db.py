"""
Abstract Database Connection Interface

This module defines the abstract base class for database connections.
"""

from abc import ABC, abstractmethod


class AbstractDBConnection(ABC):
    """Abstract base class for database connections."""

    @abstractmethod
    def create_db_instance(self, region, **kwargs):
        """Create a new database instance."""

    @abstractmethod
    def connect(self):
        """Establish connection to the database."""

    @abstractmethod
    def search(self, query_params: dict):
        """
        Perform a combined search using keywords, spatial and temporal.
        """

    @abstractmethod
    def close(self):
        """Close the database connection."""

    @abstractmethod
    def set_connection_parameters(self, params):
        """Sets the database connection parameters."""

    @abstractmethod
    def _setup_db(self):
        """Sets up the initial database state."""

    @abstractmethod
    def insert_embeddings(self, data):
        """Insert data into a specified table."""

    @abstractmethod
    def delete_embedding(self, concept_id):
        """Delete data from a specified table."""
