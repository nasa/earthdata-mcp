"""Tests for abstract_db module"""

# pylint: disable=import-error

import pytest
from util.abstract_db import AbstractDBConnection


class TestAbstractDBConnection:
    """Test suite for AbstractDBConnection"""

    def test_cannot_be_instantiated(self):
        """Test that AbstractDBConnection cannot be instantiated directly"""
        with pytest.raises(TypeError):
            AbstractDBConnection()

    def test_requires_all_methods_implemented(self):
        """Test that subclass must implement all abstract methods"""

        class IncompleteDB(AbstractDBConnection):
            """A DB class that doesn't implement all methods"""

        with pytest.raises(TypeError):
            IncompleteDB()

    def test_complete_implementation(self):
        """Test that all abstract methods can be implemented and called"""

        class CompleteDB(AbstractDBConnection):
            """A complete implementation of AbstractDBConnection"""

            def create_db_instance(self, region, **kwargs):
                """Create database instance"""
                AbstractDBConnection.create_db_instance(self, region, **kwargs)
                return "created"

            def connect(self):
                """Connect to database"""
                AbstractDBConnection.connect(self)
                return "connected"

            def search(self, query_params: dict):
                """Search database"""
                return AbstractDBConnection.search(self, query_params)

            def close(self):
                """Close database connection"""
                return AbstractDBConnection.close(self)

            def set_connection_parameters(self, params):
                """Set connection parameters"""
                return AbstractDBConnection.set_connection_parameters(self, params)

            def _setup_db(self):
                """Setup database"""
                return AbstractDBConnection._setup_db(
                    self
                )  # pylint: disable=protected-access

            def insert_embeddings(self, data):
                """Insert embeddings"""
                return AbstractDBConnection.insert_embeddings(self, data)

            def delete_embedding(self, concept_id):
                """Delete embedding"""
                return AbstractDBConnection.delete_embedding(self, concept_id)

        db = CompleteDB()
        assert db.create_db_instance("us-east-1") == "created"
        assert db.connect() == "connected"
        assert db.search({}) is None
        assert db.close() is None
        assert db.set_connection_parameters({}) is None
        assert db._setup_db() is None  # pylint: disable=protected-access
        assert db.insert_embeddings([]) is None
        assert db.delete_embedding("C123") is None
