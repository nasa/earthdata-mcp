"""PostgreSQL datastore implementation using pgvector."""

# pylint: disable=no-member  # psycopg3 has type inference issues with pylint

import json
import logging
import os
import uuid
from typing import Any

from util.database import get_db_connection
from util.datastores.base import EmbeddingDatastore
from util.models import CollectionData, ConceptType

logger = logging.getLogger(__name__)

EMBEDDINGS_TABLE = os.environ.get("EMBEDDINGS_TABLE", "embeddings")
ASSOCIATIONS_TABLE = os.environ.get("ASSOCIATIONS_TABLE", "associations")
COLLECTIONS_TABLE = os.environ.get("COLLECTIONS_TABLE", "collections")

# Which metadata column to use: "metadata" (raw) or "enriched_metadata" (improved)
METADATA_COLUMN = os.environ.get("METADATA_COLUMN", "metadata")

# Map CMR association keys to types
ASSOCIATION_TYPE_MAP = {
    "variables": "variable",
    "citations": "citation",
}


class PostgresEmbeddingDatastore(EmbeddingDatastore):
    """PostgreSQL + pgvector implementation of EmbeddingDatastore."""

    def __init__(self):
        self.conn = get_db_connection()

    def upsert_chunks(
        self,
        entity_type: ConceptType | str,
        external_id: str,
        chunks: list[tuple[str, str, list[float]]],
    ) -> int:
        """Insert or update embedding chunks for an entity."""
        if not chunks:
            return 0

        type_str = entity_type.value if hasattr(entity_type, "value") else entity_type

        with self.conn.transaction(), self.conn.cursor() as cur:
            # Delete existing chunks for this entity
            cur.execute(
                f"DELETE FROM {EMBEDDINGS_TABLE} WHERE external_id = %s AND type = %s",
                (external_id, type_str),
            )

            # Insert new chunks
            for attribute, text_content, embedding in chunks:
                cur.execute(
                    f"""
                        INSERT INTO {EMBEDDINGS_TABLE}
                            (id, type, external_id, attribute, text_content, embedding)
                        VALUES
                            (%s, %s, %s, %s, %s, %s)
                        """,
                    (
                        str(uuid.uuid4()),
                        type_str,
                        external_id,
                        attribute,
                        text_content,
                        embedding,
                    ),
                )

        logger.info("Upserted %d chunks for %s:%s", len(chunks), type_str, external_id)
        return len(chunks)

    def delete_chunks(self, external_id: str) -> int:
        """Delete all embedding chunks for an entity."""
        with self.conn.cursor() as cur:
            cur.execute(
                f"DELETE FROM {EMBEDDINGS_TABLE} WHERE external_id = %s",
                (external_id,),
            )
            return cur.rowcount

    def upsert_associations(
        self,
        left_type: ConceptType | str,
        left_id: str,
        associations: dict[str, list[str]],
    ) -> int:
        """Store associations between entities."""
        if not associations:
            return 0

        count = 0
        left_type_str = left_type.value if hasattr(left_type, "value") else left_type

        with self.conn.transaction(), self.conn.cursor() as cur:
            # Delete existing concept associations (not KMS) for this entity
            cur.execute(
                f"DELETE FROM {ASSOCIATIONS_TABLE} WHERE left_id = %s AND right_type IN ('variable', 'citation')",
                (left_id,),
            )

            for assoc_key, right_type in ASSOCIATION_TYPE_MAP.items():
                ids = associations.get(assoc_key, [])
                for right_id in ids:
                    cur.execute(
                        f"""
                        INSERT INTO {ASSOCIATIONS_TABLE}
                            (left_type, left_id, right_type, right_id)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (left_id, right_id) DO NOTHING
                        """,
                        (left_type_str, left_id, right_type, right_id),
                    )
                    count += cur.rowcount

        return count

    def delete_associations(self, external_id: str) -> int:
        """Delete all associations where this entity is involved."""
        with self.conn.cursor() as cur:
            cur.execute(
                f"""
                    DELETE FROM {ASSOCIATIONS_TABLE}
                    WHERE left_id = %s OR right_id = %s
                    """,
                (external_id, external_id),
            )
            return cur.rowcount

    def search_similar(
        self,
        embedding: list[float],
        limit: int = 10,
        entity_type: ConceptType | str | None = None,
    ) -> list[dict[str, Any]]:
        """Search for similar embeddings using pgvector."""
        with self.conn.cursor() as cur:
            if entity_type:
                type_str = entity_type.value if hasattr(entity_type, "value") else entity_type
                cur.execute(
                    f"""
                    SELECT type, external_id, attribute, text_content,
                           1 - (embedding <=> %s::vector) as similarity
                    FROM {EMBEDDINGS_TABLE}
                    WHERE type = %s
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                    """,
                    (embedding, type_str, embedding, limit),
                )
            else:
                cur.execute(
                    f"""
                    SELECT type, external_id, attribute, text_content,
                           1 - (embedding <=> %s::vector) as similarity
                    FROM {EMBEDDINGS_TABLE}
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                    """,
                    (embedding, embedding, limit),
                )

            results = []
            for row in cur.fetchall():
                results.append(
                    {
                        "type": row[0],
                        "external_id": row[1],
                        "attribute": row[2],
                        "text_content": row[3],
                        "similarity": float(row[4]),
                    }
                )

        return results

    def get_kms_embedding(self, kms_uuid: str) -> dict[str, Any] | None:
        """Get a KMS embedding by UUID."""
        with self.conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT type, external_id, attribute, text_content, embedding
                FROM {EMBEDDINGS_TABLE}
                WHERE external_id = %s AND type IN ('instruments', 'platforms', 'sciencekeywords')
                """,
                (kms_uuid,),
            )
            row = cur.fetchone()
            if row:
                return {
                    "type": row[0],
                    "external_id": row[1],
                    "attribute": row[2],
                    "text_content": row[3],
                    "embedding": list(row[4]) if row[4] is not None else None,
                }
        return None

    def upsert_kms_embedding(
        self,
        kms_uuid: str,
        scheme: str,
        term: str,
        definition: str | None,
        embedding: list[float],
    ) -> bool:
        """Insert a KMS term embedding, skipping if it already exists.

        Uses ON CONFLICT DO NOTHING to avoid deadlocks when multiple Lambdas
        try to insert the same KMS term concurrently.
        """
        text_content = f"{term}: {definition}" if definition else term

        with self.conn.cursor() as cur:
            cur.execute(
                f"""
                    INSERT INTO {EMBEDDINGS_TABLE}
                        (id, type, external_id, attribute, text_content, embedding)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (external_id, attribute) DO NOTHING
                    """,
                (str(uuid.uuid4()), scheme, kms_uuid, "term", text_content, embedding),
            )
            inserted = cur.rowcount > 0
        if inserted:
            logger.info("Inserted KMS embedding for %s/%s", scheme, term)
        return inserted

    def upsert_kms_associations(
        self,
        left_type: ConceptType | str,
        left_id: str,
        kms_refs: list[tuple[str, str]],  # List of (kms_uuid, scheme)
    ) -> int:
        """Link an entity to KMS terms."""
        if not kms_refs:
            return 0

        count = 0
        left_type_str = left_type.value if hasattr(left_type, "value") else left_type

        with self.conn.transaction(), self.conn.cursor() as cur:
            # Delete existing KMS associations for this entity
            cur.execute(
                f"""
                    DELETE FROM {ASSOCIATIONS_TABLE}
                    WHERE left_id = %s AND right_type IN ('instruments', 'platforms', 'sciencekeywords')
                    """,
                (left_id,),
            )

            # Insert new associations
            for kms_uuid, scheme in kms_refs:
                cur.execute(
                    f"""
                        INSERT INTO {ASSOCIATIONS_TABLE}
                            (left_type, left_id, right_type, right_id)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (left_id, right_id) DO NOTHING
                        """,
                    (left_type_str, left_id, scheme, kms_uuid),
                )
                count += cur.rowcount

        logger.info("Created %d KMS associations for %s:%s", count, left_type_str, left_id)
        return count

    def delete_kms_associations(self, external_id: str) -> int:
        """Delete all KMS associations for an entity."""
        with self.conn.cursor() as cur:
            cur.execute(
                f"""
                    DELETE FROM {ASSOCIATIONS_TABLE}
                    WHERE left_id = %s AND right_type IN ('instruments', 'platforms', 'sciencekeywords')
                    """,
                (external_id,),
            )
            return cur.rowcount

    def upsert_collection(self, concept_id: str, data: CollectionData) -> None:
        """
        Upsert collection metadata into the collections table.

        Args:
            concept_id: CMR concept ID
            data: CollectionData containing metadata and derived fields
        """
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO collections (
                    concept_id,
                    temporal_start,
                    temporal_end,
                    is_ongoing,
                    spatial_extent,
                    is_global,
                    metadata,
                    enriched_metadata
                ) VALUES (
                    %s, %s, %s, %s,
                    ST_GeomFromText(%s, 4326),
                    %s, %s, %s
                )
                ON CONFLICT (concept_id) DO UPDATE SET
                    temporal_start = EXCLUDED.temporal_start,
                    temporal_end = EXCLUDED.temporal_end,
                    is_ongoing = EXCLUDED.is_ongoing,
                    spatial_extent = EXCLUDED.spatial_extent,
                    is_global = EXCLUDED.is_global,
                    metadata = EXCLUDED.metadata,
                    enriched_metadata = EXCLUDED.enriched_metadata
                """,
                (
                    concept_id,
                    data.temporal_start,
                    data.temporal_end,
                    data.is_ongoing,
                    data.spatial_wkt,
                    data.is_global,
                    json.dumps(data.metadata),
                    json.dumps(data.enriched_metadata),
                ),
            )
        logger.info("Upserted collection metadata for %s", concept_id)

    def delete_collection(self, concept_id: str) -> bool:
        """Delete collection metadata from the collections table."""
        with self.conn.cursor() as cur:
            cur.execute(
                "DELETE FROM collections WHERE concept_id = %s",
                (concept_id,),
            )
            return cur.rowcount > 0

    def get_collections_for_entities(self, entities: list[tuple[str, str]]) -> dict[str, list[str]]:
        """
        Get all collections associated with given entities.

        Args:
            entities: List of (entity_id, entity_type) tuples

        Returns:
            Dict mapping entity_id to list of collection IDs
        """
        if not entities:
            return {}

        results: dict[str, list[str]] = {eid: [] for eid, _ in entities}

        # Query associations to find collections linked to these entities
        with self.conn.cursor() as cur:
            for entity_id, entity_type in entities:
                cur.execute(
                    f"""
                    SELECT DISTINCT right_id FROM {ASSOCIATIONS_TABLE}
                    WHERE left_id = %s AND left_type = %s AND right_type = 'collection'
                    """,
                    (entity_id, entity_type),
                )
                collection_ids = [row[0] for row in cur.fetchall()]
                results[entity_id] = collection_ids

        return results

    def fetch_collections_by_ids(
        self,
        concept_ids: list[str],
        temporal_start: Any | None = None,
        temporal_end: Any | None = None,
        spatial_wkt: str | None = None,
    ) -> dict[str, dict[str, Any]]:
        """
        Fetch collection data for a list of concept IDs with optional filtering.

        Uses the METADATA_COLUMN environment variable to determine which
        metadata column to read (default: "metadata", alternative: "enriched_metadata").

        Args:
            concept_ids: List of CMR concept IDs
            temporal_start: Optional start date - exclude collections that end before this
            temporal_end: Optional end date - exclude collections that start after this
            spatial_wkt: Optional WKT geometry - exclude collections that don't intersect

        Returns:
            Dict mapping concept_id to collection data dict containing:
            - temporal_start, temporal_end, is_ongoing, is_global (denormalized)
            - metadata: the UMM-C metadata dict for parsing
        """
        if not concept_ids:
            return {}

        results: dict[str, dict[str, Any]] = {}

        # Build query with optional constraint filters
        id_params = ",".join(["%s"] * len(concept_ids))
        where_clauses = [f"concept_id IN ({id_params})"]
        params: list[Any] = list(concept_ids)

        # Temporal filtering: collection must overlap with constraint range
        if temporal_start is not None:
            # Collection must not end before our start (or be ongoing, or have no end)
            where_clauses.append(
                "(temporal_end >= %s OR temporal_end IS NULL OR is_ongoing = true)"
            )
            params.append(temporal_start)

        if temporal_end is not None:
            # Collection must not start after our end (or have no start)
            where_clauses.append("(temporal_start <= %s OR temporal_start IS NULL)")
            params.append(temporal_end)

        # Spatial filtering: collection must intersect with constraint geometry
        if spatial_wkt is not None:
            # Use ST_Intersects for spatial overlap, or include global collections
            where_clauses.append(
                "(is_global = true OR ST_Intersects(spatial_extent, ST_GeomFromText(%s, 4326)))"
            )
            params.append(spatial_wkt)

        where_sql = " AND ".join(where_clauses)

        with self.conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    concept_id,
                    temporal_start,
                    temporal_end,
                    is_ongoing,
                    is_global,
                    {METADATA_COLUMN}
                FROM {COLLECTIONS_TABLE}
                WHERE {where_sql}
                """,
                params,
            )

            for row in cur.fetchall():
                concept_id = row[0]
                results[concept_id] = {
                    "temporal_start": row[1],
                    "temporal_end": row[2],
                    "is_ongoing": row[3],
                    "is_global": row[4],
                    "metadata": row[5] if row[5] else {},
                }

        logger.debug(
            "Fetched collection data for %d/%d collections (temporal=%s, spatial=%s)",
            len(results),
            len(concept_ids),
            temporal_start is not None or temporal_end is not None,
            spatial_wkt is not None,
        )

        return results

    def close(self) -> None:
        """Close the database connection."""
        if self.conn:
            self.conn.close()
