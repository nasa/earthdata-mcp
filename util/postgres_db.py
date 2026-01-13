"""
PostgreSQL Database Connection Module

This module provides a PostgreSQL implementation of the AbstractDBConnection interface
for managing vector embeddings with spatial and temporal search capabilities.
"""

import json
import os
import logging
from datetime import datetime

import boto3
import psycopg2
from psycopg2 import DatabaseError

from util.get_secret import get_secret
from util.abstract_db import AbstractDBConnection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PostgresDBConnection(AbstractDBConnection):
    """
    A PostgreSQL database connection class that implements the AbstractDBConnection interface.
    """

    def __init__(self):
        self.db_params = {
            "dbname": os.getenv("DB_NAME"),
            "user": os.getenv("DB_USERNAME"),
            "password": os.getenv("DB_PASSWORD"),
            "host": os.getenv("DB_HOST"),
            "port": "5432",
        }
        self.connection = None
        self.embeddings_table = os.getenv("EMBEDDINGS_TABLE", "vector_embeddings")

        secret = os.getenv("SECRET_ID")
        if secret:
            db_secret = get_secret(secret)
            self.db_params["password"] = db_secret["password"]

    def set_connection_parameters(self, params):
        for config_item in params:
            if config_item in self.db_params:
                self.db_params[config_item] = params[config_item]
            elif config_item == "embeddings_table":
                self.embeddings_table = params[config_item]

    def create_db_instance(self, region, **kwargs):
        """
        Create a new RDS database instance in the specified AWS region.

        This method uses the AWS SDK (boto3) to create a new RDS instance with the
        provided parameters.

        Args:
            region (str): The AWS region where the RDS instance should be created.
            **kwargs: Additional keyword arguments for RDS instance configuration.
        """

        rds_client = boto3.client("rds", region_name=region)

        try:
            rds_client.create_db_instance(**kwargs)
            logger.info("Creating RDS instance '%s'", kwargs["DBInstanceIdentifier"])
        except Exception as e:
            logger.error("Unexpected error creating RDS instance: %s", str(e))
            raise

    def _setup_db(self):
        enable_extensions_query = """
        CREATE EXTENSION IF NOT EXISTS vector;
        CREATE EXTENSION IF NOT EXISTS postgis;
        """

        # Base schema definition — single source of truth
        expected_columns = {
            "concept_id": "TEXT PRIMARY KEY",
            "sentence_embedding": "VECTOR",
            "summary": "TEXT",
            "geo_spatial": "GEOMETRY(GEOMETRY, 4326)",
            "start_time": "TIMESTAMP",
            "end_time": "TIMESTAMP",
        }

        create_table_query = f"""
        CREATE TABLE IF NOT EXISTS {self.embeddings_table} (
            {", ".join([f"{col} {dtype}" for col, dtype in expected_columns.items()])}
        );
        """

        try:
            with self.connection:
                with self.connection.cursor() as curr:
                    curr.execute(enable_extensions_query)
                    curr.execute(create_table_query)

                    # Get existing columns in the table
                    curr.execute(
                        "SELECT column_name "
                        "FROM information_schema.columns "
                        "WHERE table_name = %s;",
                        (self.embeddings_table,),
                    )
                    existing_columns = {row[0] for row in curr.fetchall()}

                    # Find columns that need to be added
                    missing_columns = {
                        col: dtype
                        for col, dtype in expected_columns.items()
                        if col not in existing_columns
                    }

                    # Add any missing columns dynamically
                    if missing_columns:
                        alter_statements = ", ".join(
                            [
                                f"ADD COLUMN IF NOT EXISTS {col} {dtype}"
                                for col, dtype in missing_columns.items()
                            ]
                        )
                        alter_query = (
                            f"ALTER TABLE {self.embeddings_table} "
                            f"{alter_statements};"
                        )
                        curr.execute(alter_query)
                        logger.info(
                            "Schema updated: added missing columns %s",
                            list(missing_columns.keys()),
                        )

            logger.info("Database setup completed successfully.")
        except psycopg2.Error as e:
            self.close()
            raise ConnectionError(f"Failed setting up database: {e}") from e

    def connect(self):
        """
        Establish a connection to the PostgreSQL database.

        This method attempts to create a connection to the database using the parameters
        provided during the class initialization. If successful, it sets up the connection
        and cursor attributes.
        """
        try:
            self.connection = psycopg2.connect(**self.db_params)
            logger.info("Successfully connected to the database.")
        except psycopg2.Error as e:
            self.connection = None
            raise ConnectionError(f"Failed to connect to the database: {e}") from e
        self._setup_db()

    def insert_embeddings(self, data):
        """
        Insert data into the specified table in the PostgreSQL database.

        This method takes a list of data entries and inserts them into the specified table.
        It assumes that the data structure matches the table schema.

        Args:
            data (list): A list of dictionaries, where each dictionary represents a row to be
                         inserted. The keys of the dictionary should match the column names
                         in the table.

        Returns:
            bool: True if the insertion was successful, False otherwise.
        """
        if not self.connection:
            raise ConnectionError("Database connection is not established.")

        query = f"""
            INSERT INTO {self.embeddings_table}
            (concept_id, sentence_embedding, summary, geo_spatial, start_time, end_time)
            VALUES (%s, %s, %s, ST_GeomFromText(%s, 4326), %s, %s) 
            ON CONFLICT (concept_id) DO UPDATE
            SET sentence_embedding = EXCLUDED.sentence_embedding,
                summary = EXCLUDED.summary,
                geo_spatial = EXCLUDED.geo_spatial,
                start_time = EXCLUDED.start_time,
                end_time = EXCLUDED.end_time;
            """
        try:
            with self.connection:
                with self.connection.cursor() as curr:
                    for item in data:
                        curr.execute(
                            query,
                            (
                                item["concept_id"],
                                item["sentence_embedding"],
                                item.get("summary", None),
                                item.get("geometry", None),  # WKT format
                                item.get("start_time", None),
                                item.get("end_time", None),
                            ),
                        )

        except psycopg2.Error as e:
            raise ConnectionError(f"Failed to insert data into the table: {e}") from e

    def delete_embedding(self, concept_id):
        """
        Delete a record from the database based on the concept_id.

        Args:
            concept_id (str): The concept_id of the record to be deleted.

        Returns:
            bool: True if the deletion was successful, False otherwise.
        """
        if not self.connection:
            raise ConnectionError("Database connection is not established.")

        query = f"""
            DELETE FROM {self.embeddings_table}
            WHERE concept_id = %s
        """

        try:
            with self.connection:
                with self.connection.cursor() as curr:
                    curr.execute(query, (concept_id,))
                    if curr.rowcount == 0:
                        return False
                    return True
        except psycopg2.Error as e:
            raise ConnectionError(f"Failed to delete record from the table: {e}") from e

    def _normalize_date(self, date_str):
        """
        Convert various date formats to PostgreSQL timestamp format.
        Handles ISO 8601 formats with/without timezone.

        Args:
            date_str (str): Date string in various formats

        Returns:
            str: Date in 'YYYY-MM-DD HH:MM:SS' format
        """
        try:
            # Handle ISO 8601 with 'Z' or timezone offset
            if "T" in date_str:
                # Remove 'Z' and parse
                date_str = date_str.replace("Z", "+00:00")
                dt = datetime.fromisoformat(date_str)
            else:
                # Handle plain datetime format
                dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")

            # Return in PostgreSQL timestamp format (without timezone)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError as e:
            logger.error("Failed to parse date '%s': %s", date_str, e)
            raise ValueError(f"Invalid date format: {date_str}") from e

    def search(self, query_params):  # pylint: disable=too-many-locals
        """
        Perform a combined search using cosine similarity (keyword), spatial, and temporal filters.

        Args:
            query_params (dict): A dictionary containing search parameters:
                - query_embedding (list): The embedding vector to compare against.
                - geometry (str, optional): WKT representation of geometry for spatial filtering.
                - start_date (str, optional): Start date for temporal filtering.
                - end_date (str, optional): End date for temporal filtering.
                - query_size (int, optional): Number of results to return. Defaults to 10.

        Returns:
        list: A list of tuples containing search results.
        """
        if not self.connection:
            logger.error("Database connection is not established.")
            return []

        query_embedding = query_params.get("query_embedding")
        geometry = query_params.get("geometry")
        start_date = query_params.get("start_date", None)
        end_date = query_params.get("end_date", None)
        query_size = int(query_params.get("query_size", 10))
        page = int(query_params.get("page", 0))
        query_fields = query_params.get(
            "query_fields", ["concept_id", "start_time", "end_time"]
        )
        embedding_field = query_params.get("embedding_field", "sentence_embedding")
        offset = page * query_size

        # Normalize date formats
        if start_date:
            start_date = self._normalize_date(start_date)
        if end_date:
            end_date = self._normalize_date(end_date)

        try:
            with self.connection:
                with self.connection.cursor() as curr:
                    # Build WHERE clause for pre-filtering
                    where_conditions = []
                    params = []

                    if geometry:
                        spatial_wkt = geometry.wkt
                        if not spatial_wkt.startswith("SRID="):
                            spatial_wkt = f"SRID=4326;{spatial_wkt}"
                        where_conditions.append(
                            "(geo_spatial IS NULL OR "
                            "ST_Intersects(geo_spatial, ST_GeomFromEWKT(%s)))"
                        )
                        params.append(spatial_wkt)

                    if start_date and end_date:
                        # Event overlaps if it starts before search ends
                        # AND ends after search starts
                        where_conditions.append(
                            "((start_time IS NULL OR start_time <= %s::timestamp) "
                            "AND (end_time IS NULL OR end_time >= %s::timestamp))"
                        )
                        params.extend([end_date, start_date])
                    elif start_date:
                        # Only start date: event must end after (or be ongoing after) start_date
                        where_conditions.append(
                            "(end_time IS NULL OR end_time >= %s::timestamp)"
                        )
                        params.append(start_date)
                    elif end_date:
                        # Only end date: event must start before end_date
                        where_conditions.append(
                            "(start_time IS NULL OR start_time <= %s::timestamp)"
                        )
                        params.append(end_date)

                    # Build the query with CTE for filtering first
                    where_clause = (
                        " AND ".join(where_conditions) if where_conditions else "1=1"
                    )

                    query = f"""
                    WITH filtered AS (
                        SELECT *
                        FROM {self.embeddings_table}
                        WHERE {where_clause}
                    )
                    SELECT
                        {", ".join(query_fields)},
                        1 - ({embedding_field} <=> %s) AS similarity
                    FROM filtered
                    ORDER BY similarity DESC
                    LIMIT {query_size} OFFSET {offset}
                    """

                    # Add embedding parameter at the end
                    all_params = params + [json.dumps(query_embedding)]

                    curr.execute(query, tuple(all_params))
                    results = curr.fetchall()
                    return results
        except psycopg2.Error as e:
            raise DatabaseError(f"Failed to perform search: {e}") from e

    def close(self):
        """
        Close the database connection and cursor.

        This method ensures that both the cursor and the database connection
        are properly closed, releasing any resources they might be holding.
        """
        if self.connection:
            self.connection.close()
