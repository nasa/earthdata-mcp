"""Tests for postgres_db module"""

from unittest.mock import patch, Mock, MagicMock  # pylint: disable=import-error

import pytest  # pylint: disable=import-error
import psycopg2  # pylint: disable=import-error
from util.postgres_db import PostgresDBConnection  # pylint: disable=import-error


def mock_connection_with_cursor(rowcount=1, fetchall_result=None):
    """Create a mock database connection with a cursor for testing."""
    cursor = MagicMock()
    cursor.rowcount = rowcount
    cursor.fetchall.return_value = fetchall_result or []

    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cursor
    conn.__enter__.return_value = conn

    return conn, cursor


@pytest.fixture
def db():
    """Fixture to create a PostgresDBConnection instance."""
    return PostgresDBConnection()


class TestPostgresDBConnection:
    """Tests for PostgresDBConnection class"""

    @patch("util.postgres_db.os.getenv")
    def test_init_without_secret(self, mock_getenv):
        """Test initialization without AWS secret"""
        mock_getenv.side_effect = lambda key, default=None: {
            "DB_NAME": "test_db",
            "DB_USERNAME": "test_user",
            "DB_PASSWORD": "test_pass",
            "DB_HOST": "localhost",
            "EMBEDDINGS_TABLE": "embeddings",
            "SECRET_ID": None,
        }.get(key, default)

        db = PostgresDBConnection()

        assert db.db_params["dbname"] == "test_db"
        assert db.db_params["user"] == "test_user"
        assert db.db_params["password"] == "test_pass"
        assert db.db_params["host"] == "localhost"
        assert db.db_params["port"] == "5432"
        assert db.embeddings_table == "embeddings"

    @patch("util.postgres_db.get_secret")
    @patch("util.postgres_db.os.getenv")
    def test_init_with_secret(self, mock_getenv, mock_get_secret):
        """Test initialization with AWS secret"""
        mock_getenv.side_effect = lambda key, default=None: {
            "DB_NAME": "test_db",
            "DB_USERNAME": "test_user",
            "DB_PASSWORD": "old_pass",
            "DB_HOST": "localhost",
            "SECRET_ID": "my-secret",
        }.get(key, default)

        mock_get_secret.return_value = {"password": "secret_pass"}

        db = PostgresDBConnection()

        assert db.db_params["password"] == "secret_pass"
        mock_get_secret.assert_called_once_with("my-secret")

    @patch("util.postgres_db.os.getenv")
    def test_set_connection_parameters(self, mock_getenv):
        """Test setting connection parameters"""
        mock_getenv.return_value = None
        db = PostgresDBConnection()

        params = {
            "dbname": "new_db",
            "user": "new_user",
            "host": "new_host",
            "embeddings_table": "new_table",
        }

        db.set_connection_parameters(params)

        assert db.db_params["dbname"] == "new_db"
        assert db.db_params["user"] == "new_user"
        assert db.db_params["host"] == "new_host"
        assert db.embeddings_table == "new_table"

    @patch("util.postgres_db.boto3.client")
    @patch("util.postgres_db.os.getenv")
    def test_create_db_instance_success(self, mock_getenv, mock_boto_client):
        """Test creating RDS instance successfully"""
        mock_getenv.return_value = None
        mock_rds = Mock()
        mock_boto_client.return_value = mock_rds

        db = PostgresDBConnection()
        db.create_db_instance(
            "us-east-1", DBInstanceIdentifier="test-db", DBInstanceClass="db.t3.micro"
        )

        mock_boto_client.assert_called_once_with("rds", region_name="us-east-1")
        mock_rds.create_db_instance.assert_called_once()

    @patch("util.postgres_db.boto3.client")
    @patch("util.postgres_db.os.getenv")
    def test_create_db_instance_failure(self, mock_getenv, mock_boto_client):
        """Test handling RDS instance creation failure"""
        mock_getenv.return_value = None
        mock_rds = Mock()
        mock_rds.create_db_instance.side_effect = Exception("AWS error")
        mock_boto_client.return_value = mock_rds

        db = PostgresDBConnection()

        with pytest.raises(Exception, match="AWS error"):
            db.create_db_instance("us-east-1", DBInstanceIdentifier="test-db")

    @patch("util.postgres_db.psycopg2.connect")
    @patch("util.postgres_db.os.getenv")
    def test_connect_success(self, mock_getenv, mock_connect):
        """Test successful database connection"""
        mock_getenv.return_value = None
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []
        mock_connect.return_value = mock_conn

        db = PostgresDBConnection()
        db.connect()

        assert db.connection is not None
        mock_connect.assert_called_once()
        # _setup_db should be called
        assert mock_cursor.execute.called

    @patch("util.postgres_db.psycopg2.connect")
    @patch("util.postgres_db.os.getenv")
    def test_connect_failure(self, mock_getenv, mock_connect):
        """Test database connection failure"""
        mock_getenv.return_value = None
        mock_connect.side_effect = psycopg2.Error("Connection failed")

        db = PostgresDBConnection()

        with pytest.raises(ConnectionError, match="Failed to connect"):
            db.connect()

        assert db.connection is None

    @patch("util.postgres_db.psycopg2.connect")
    @patch("util.postgres_db.os.getenv")
    def test_setup_db_creates_extensions(self, mock_getenv, mock_connect):
        """Test that _setup_db creates required extensions"""
        mock_getenv.side_effect = lambda key, default=None: {
            "EMBEDDINGS_TABLE": "vector_embeddings"
        }.get(key, default)

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        # Return all expected columns as existing (no missing columns)
        mock_cursor.fetchall.return_value = [
            ("concept_id",),
            ("sentence_embedding",),
            ("summary",),
            ("geo_spatial",),
            ("start_time",),
            ("end_time",),
        ]
        mock_connect.return_value = mock_conn

        db = PostgresDBConnection()
        db.connect()

        # Verify extension creation query was called
        calls = [call[0][0] for call in mock_cursor.execute.call_args_list]
        assert any(
            "CREATE EXTENSION IF NOT EXISTS vector" in call for call in calls
        ), "Vector extension should be created"
        assert any(
            "CREATE EXTENSION IF NOT EXISTS postgis" in call for call in calls
        ), "PostGIS extension should be created"

    @patch("util.postgres_db.psycopg2.connect")
    @patch("util.postgres_db.os.getenv")
    def test_setup_db_creates_table(self, mock_getenv, mock_connect):
        """Test that _setup_db creates the embeddings table"""
        mock_getenv.side_effect = lambda key, default=None: {
            "EMBEDDINGS_TABLE": "vector_embeddings"
        }.get(key, default)

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [
            ("concept_id",),
            ("sentence_embedding",),
            ("summary",),
            ("geo_spatial",),
            ("start_time",),
            ("end_time",),
        ]
        mock_connect.return_value = mock_conn

        db = PostgresDBConnection()
        db.connect()

        # Verify table creation query was called
        calls = [call[0][0] for call in mock_cursor.execute.call_args_list]
        table_creation_calls = [
            call
            for call in calls
            if "CREATE TABLE IF NOT EXISTS vector_embeddings" in call
        ]
        assert len(table_creation_calls) > 0, "Table creation query should be executed"

        # Verify all required columns are in the schema
        table_query = table_creation_calls[0]
        assert "concept_id" in table_query
        assert "sentence_embedding" in table_query
        assert "summary" in table_query
        assert "geo_spatial" in table_query
        assert "start_time" in table_query
        assert "end_time" in table_query

    @patch("util.postgres_db.psycopg2.connect")
    @patch("util.postgres_db.os.getenv")
    def test_setup_db_adds_missing_columns(self, mock_getenv, mock_connect):
        """Test that _setup_db adds missing columns to existing table"""
        mock_getenv.side_effect = lambda key, default=None: {
            "EMBEDDINGS_TABLE": "vector_embeddings"
        }.get(key, default)

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        # Simulate table with only some columns existing
        mock_cursor.fetchall.return_value = [
            ("concept_id",),
            ("sentence_embedding",),
            ("summary",),
            # Missing: geo_spatial, start_time, end_time
        ]
        mock_connect.return_value = mock_conn

        db = PostgresDBConnection()
        db.connect()

        # Verify ALTER TABLE was called to add missing columns
        calls = [call[0][0] for call in mock_cursor.execute.call_args_list]
        alter_calls = [call for call in calls if "ALTER TABLE" in call]

        assert len(alter_calls) > 0, "ALTER TABLE should be called for missing columns"
        alter_query = alter_calls[0]
        assert "ADD COLUMN IF NOT EXISTS" in alter_query
        assert "geo_spatial" in alter_query
        assert "start_time" in alter_query
        assert "end_time" in alter_query

    @patch("util.postgres_db.psycopg2.connect")
    @patch("util.postgres_db.os.getenv")
    def test_setup_db_no_alter_when_all_columns_exist(self, mock_getenv, mock_connect):
        """Test that _setup_db doesn't alter table when all columns exist"""
        mock_getenv.side_effect = lambda key, default=None: {
            "EMBEDDINGS_TABLE": "vector_embeddings"
        }.get(key, default)

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        # All columns exist
        mock_cursor.fetchall.return_value = [
            ("concept_id",),
            ("sentence_embedding",),
            ("summary",),
            ("geo_spatial",),
            ("start_time",),
            ("end_time",),
        ]
        mock_connect.return_value = mock_conn

        db = PostgresDBConnection()
        db.connect()

        # Verify ALTER TABLE was NOT called
        calls = [call[0][0] for call in mock_cursor.execute.call_args_list]
        alter_calls = [call for call in calls if "ALTER TABLE" in call]

        assert (
            len(alter_calls) == 0
        ), "ALTER TABLE should not be called when all columns exist"

    @patch("util.postgres_db.psycopg2.connect")
    @patch("util.postgres_db.os.getenv")
    def test_setup_db_queries_existing_columns(self, mock_getenv, mock_connect):
        """Test that _setup_db queries information_schema for existing columns"""
        mock_getenv.side_effect = lambda key, default=None: {
            "EMBEDDINGS_TABLE": "vector_embeddings"
        }.get(key, default)

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [("concept_id",)]
        mock_connect.return_value = mock_conn

        db = PostgresDBConnection()
        db.connect()

        # Verify query to information_schema.columns was made
        calls = [call[0][0] for call in mock_cursor.execute.call_args_list]
        info_schema_calls = [
            call for call in calls if "information_schema.columns" in call
        ]

        assert (
            len(info_schema_calls) > 0
        ), "Should query information_schema.columns to check existing columns"
        # Verify the table name parameter was passed
        call_args = mock_cursor.execute.call_args_list
        # Find the information_schema query call
        for call_arg in call_args:
            if len(call_arg[0]) > 0 and "information_schema.columns" in call_arg[0][0]:
                if len(call_arg[0]) > 1:
                    # Check that table name parameter is passed
                    assert call_arg[0][1] == (
                        "vector_embeddings",
                    ), "Table name should be passed as parameter"

    @patch("util.postgres_db.psycopg2.connect")
    @patch("util.postgres_db.os.getenv")
    def test_setup_db_handles_psycopg2_error(self, mock_getenv, mock_connect):
        """Test that _setup_db handles psycopg2 errors and closes connection"""
        mock_getenv.side_effect = lambda key, default=None: {
            "EMBEDDINGS_TABLE": "vector_embeddings"
        }.get(key, default)

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        # Simulate psycopg2 error during extension creation
        mock_cursor.execute.side_effect = psycopg2.Error("Extension creation failed")
        mock_connect.return_value = mock_conn

        db = PostgresDBConnection()

        with pytest.raises(ConnectionError, match="Failed setting up database"):
            db.connect()

        # Verify connection was closed after error
        mock_conn.close.assert_called_once()

    @patch("util.postgres_db.psycopg2.connect")
    @patch("util.postgres_db.os.getenv")
    def test_setup_db_error_during_alter_table(self, mock_getenv, mock_connect):
        """Test that _setup_db handles errors during ALTER TABLE"""
        mock_getenv.side_effect = lambda key, default=None: {
            "EMBEDDINGS_TABLE": "vector_embeddings"
        }.get(key, default)

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        # First two execute calls succeed (extensions, create table)
        # Third call gets columns (missing some)
        # Fourth call (ALTER TABLE) fails
        execute_count = [0]

        def execute_side_effect(*args, **kwargs):  # pylint: disable=unused-argument
            """Side effect function to simulate ALTER TABLE failure."""
            execute_count[0] += 1
            if execute_count[0] == 4:  # ALTER TABLE call
                raise psycopg2.Error("ALTER TABLE failed")

        mock_cursor.execute.side_effect = execute_side_effect
        mock_cursor.fetchall.return_value = [("concept_id",)]  # Missing columns
        mock_connect.return_value = mock_conn

        db = PostgresDBConnection()

        with pytest.raises(ConnectionError, match="Failed setting up database"):
            db.connect()

        # Verify connection was closed after error
        mock_conn.close.assert_called_once()

    @patch("util.postgres_db.psycopg2.connect")
    @patch("util.postgres_db.os.getenv")
    def test_setup_db_with_custom_table_name(self, mock_getenv, mock_connect):
        """Test that _setup_db uses custom embeddings table name"""
        mock_getenv.side_effect = lambda key, default=None: {
            "EMBEDDINGS_TABLE": "custom_embeddings"
        }.get(key, default)

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [("concept_id",)]
        mock_connect.return_value = mock_conn

        db = PostgresDBConnection()
        db.connect()

        # Verify custom table name is used in queries
        calls = [call[0][0] for call in mock_cursor.execute.call_args_list]
        table_creation_calls = [
            call for call in calls if "CREATE TABLE IF NOT EXISTS" in call
        ]

        assert len(table_creation_calls) > 0
        assert "custom_embeddings" in table_creation_calls[0]

    @patch("util.postgres_db.psycopg2.connect")
    @patch("util.postgres_db.os.getenv")
    def test_setup_db_uses_transaction(self, mock_getenv, mock_connect):
        """Test that _setup_db uses connection as context manager (transaction)"""
        mock_getenv.side_effect = lambda key, default=None: {
            "EMBEDDINGS_TABLE": "vector_embeddings"
        }.get(key, default)

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [("concept_id",)]
        mock_connect.return_value = mock_conn

        db = PostgresDBConnection()
        db.connect()

        # Verify connection was used as context manager (with statement)
        mock_conn.__enter__.assert_called()
        mock_conn.__exit__.assert_called()


class TestInsertEmbeddings:
    """Tests for insert_embeddings method."""

    def test_success(self, db):
        """Test successful insertion of embeddings."""
        conn, cursor = mock_connection_with_cursor()
        db.connection = conn

        data = [
            {
                "concept_id": "C1",
                "sentence_embedding": [0.1, 0.2],
                "summary": "summary",
                "geometry": "POINT(1 1)",
                "start_time": "2020-01-01",
                "end_time": "2020-12-31",
            }
        ]

        db.insert_embeddings(data)

        assert cursor.execute.call_count == 1

    def test_no_connection(self, db):
        """Test insertion fails when no connection is available."""
        db.connection = None

        with pytest.raises(ConnectionError):
            db.insert_embeddings([])

    def test_db_error(self, db):
        """Test insertion fails when database error occurs."""
        conn, cursor = mock_connection_with_cursor()
        cursor.execute.side_effect = psycopg2.Error("insert failed")
        db.connection = conn

        with pytest.raises(ConnectionError):
            db.insert_embeddings([{"concept_id": "C1", "sentence_embedding": []}])


class TestDeleteEmbedding:
    """Tests for delete_embedding method."""

    def test_success(self, db):
        """Test successful deletion of an embedding."""
        conn, cursor = mock_connection_with_cursor(rowcount=1)
        db.connection = conn

        result = db.delete_embedding("C1")

        assert result is True
        cursor.execute.assert_called_once()

    def test_not_found(self, db):
        """Test deletion when embedding is not found."""
        conn, _ = mock_connection_with_cursor(rowcount=0)
        db.connection = conn

        result = db.delete_embedding("C404")

        assert result is False

    def test_no_connection(self, db):
        """Test deletion fails when no connection is available."""
        db.connection = None

        with pytest.raises(ConnectionError):
            db.delete_embedding("C1")

    def test_db_error(self, db):
        """Test deletion fails when database error occurs."""
        conn, cursor = mock_connection_with_cursor()
        cursor.execute.side_effect = psycopg2.Error("delete failed")
        db.connection = conn

        with pytest.raises(ConnectionError):
            db.delete_embedding("C1")


class TestNormalizeDate:
    """Tests for _normalize_date method."""

    def test_iso_z(self, db):
        """Test normalization of ISO date with Z timezone."""
        # pylint: disable=protected-access
        result = db._normalize_date("2023-01-01T10:00:00Z")
        assert result == "2023-01-01 10:00:00"

    def test_iso_offset(self, db):
        """Test normalization of ISO date with timezone offset."""
        # pylint: disable=protected-access
        result = db._normalize_date("2023-01-01T10:00:00+00:00")
        assert result == "2023-01-01 10:00:00"

    def test_plain_datetime(self, db):
        """Test normalization of plain datetime string."""
        # pylint: disable=protected-access
        result = db._normalize_date("2023-01-01 10:00:00")
        assert result == "2023-01-01 10:00:00"

    def test_invalid_format(self, db):
        """Test normalization with invalid date format."""
        # pylint: disable=protected-access
        with pytest.raises(ValueError):
            db._normalize_date("not-a-date")


class TestSearch:
    """Tests for search method."""

    def test_no_connection(self, db):
        """Test search returns empty list when no connection is available."""
        db.connection = None

        result = db.search({})

        assert result == []

    def test_embedding_only(self, db):
        """Test search with embedding query only."""
        conn, cursor = mock_connection_with_cursor(
            fetchall_result=[("C1", None, None, 0.9)]
        )
        db.connection = conn

        result = db.search(
            {
                "query_embedding": [0.1, 0.2],
                "query_size": 5,
            }
        )

        assert len(result) == 1
        cursor.execute.assert_called_once()

    def test_geometry_and_temporal(self, db):
        """Test search with geometry and temporal filters."""
        conn, cursor = mock_connection_with_cursor(
            fetchall_result=[("C1", None, None, 0.95)]
        )
        db.connection = conn

        geometry = MagicMock()
        geometry.wkt = "POLYGON((1 1,2 2,3 3))"

        result = db.search(
            {
                "query_embedding": [0.1],
                "geometry": geometry,
                "start_date": "2020-01-01T00:00:00Z",
                "end_date": "2020-12-31T00:00:00Z",
                "query_size": 10,
                "page": 0,
            }
        )

        assert result
        cursor.execute.assert_called_once()

        # Verify SRID prefix logic
        params = cursor.execute.call_args[0][1]
        assert any("SRID=4326;" in p for p in params)

    def test_search_only_start_date(self, db):
        """Test search with only start date filter."""
        conn, cursor = mock_connection_with_cursor(
            fetchall_result=[("C1", None, None, 0.88)]
        )
        db.connection = conn

        result = db.search(
            {
                "query_embedding": [0.1, 0.2],
                "start_date": "2020-01-01T00:00:00Z",
                "query_size": 5,
            }
        )

        assert result
        cursor.execute.assert_called_once()

        sql, params = cursor.execute.call_args[0]

        # Assert correct WHERE clause path was taken
        assert "end_time IS NULL OR end_time >= %s::timestamp" in sql
        assert "start_time IS NULL OR start_time <= %s::timestamp" not in sql

        # Assert normalized date param
        assert "2020-01-01 00:00:00" in params

    def test_search_only_end_date(self, db):
        """Test search with only end date filter."""
        conn, cursor = mock_connection_with_cursor(
            fetchall_result=[("C2", None, None, 0.91)]
        )
        db.connection = conn

        result = db.search(
            {
                "query_embedding": [0.3],
                "end_date": "2021-12-31T00:00:00Z",
                "query_size": 5,
            }
        )

        assert result
        cursor.execute.assert_called_once()

        sql, params = cursor.execute.call_args[0]

        # Assert correct WHERE clause path was taken
        assert "start_time IS NULL OR start_time <= %s::timestamp" in sql
        assert "end_time IS NULL OR end_time >= %s::timestamp" not in sql

        # Assert normalized date param
        assert "2021-12-31 00:00:00" in params

    def test_db_error(self, db):
        """Test search fails when database error occurs."""
        conn, cursor = mock_connection_with_cursor()
        cursor.execute.side_effect = psycopg2.Error("search failed")
        db.connection = conn

        with pytest.raises(psycopg2.DatabaseError):
            db.search({"query_embedding": [0.1]})
