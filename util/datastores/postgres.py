"""PostgreSQL datastore implementation using pgvector."""

# pylint: disable=no-member  # psycopg3 has type inference issues with pylint

import logging
import os
import uuid
from typing import Any

from util.database import get_db_connection
from util.datastores.base import EmbeddingDatastore

logger = logging.getLogger(__name__)

EMBEDDINGS_TABLE = os.environ.get("EMBEDDINGS_TABLE", "concept_embeddings")
ASSOCIATIONS_TABLE = os.environ.get("ASSOCIATIONS_TABLE", "concept_associations")
KMS_EMBEDDINGS_TABLE = os.environ.get("KMS_EMBEDDINGS_TABLE", "kms_embeddings")
KMS_ASSOCIATIONS_TABLE = os.environ.get("KMS_ASSOCIATIONS_TABLE", "concept_kms_associations")

# Map CMR association keys to concept types
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
        concept_type: str,
        concept_id: str,
        chunks: list[tuple[str, str, list[float]]],
    ) -> int:
        """Insert or update embedding chunks for a concept."""
        if not chunks:
            return 0

        with self.conn.cursor() as cur:
            # Delete existing chunks for this concept
            cur.execute(
                f"DELETE FROM {EMBEDDINGS_TABLE} WHERE concept_id = %s",
                (concept_id,),
            )

            # Insert new chunks
            for attribute, text_content, embedding in chunks:
                cur.execute(
                    f"""
                    INSERT INTO {EMBEDDINGS_TABLE}
                        (id, concept_type, concept_id, attribute, text_content, embedding)
                    VALUES
                        (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        str(uuid.uuid4()),
                        concept_type,
                        concept_id,
                        attribute,
                        text_content,
                        embedding,
                    ),
                )

        self.conn.commit()
        logger.info("Upserted %d chunks for %s", len(chunks), concept_id)
        return len(chunks)

    def delete_chunks(self, concept_id: str) -> int:
        """Delete all embedding chunks for a concept."""
        with self.conn.cursor() as cur:
            cur.execute(
                f"DELETE FROM {EMBEDDINGS_TABLE} WHERE concept_id = %s",
                (concept_id,),
            )
            deleted = cur.rowcount
        self.conn.commit()
        return deleted

    def upsert_associations(
        self,
        concept_type: str,
        concept_id: str,
        associations: dict[str, list[str]],
    ) -> int:
        """Store concept associations."""
        if not associations:
            return 0

        count = 0
        with self.conn.cursor() as cur:
            # Delete existing associations for this concept
            cur.execute(
                f"DELETE FROM {ASSOCIATIONS_TABLE} WHERE left_concept_id = %s",
                (concept_id,),
            )

            for assoc_key, right_concept_type in ASSOCIATION_TYPE_MAP.items():
                concept_ids = associations.get(assoc_key, [])
                for right_concept_id in concept_ids:
                    cur.execute(
                        f"""
                        INSERT INTO {ASSOCIATIONS_TABLE}
                            (left_concept_type, left_concept_id, right_concept_type, right_concept_id)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (left_concept_id, right_concept_id) DO NOTHING
                        """,
                        (
                            concept_type,
                            concept_id,
                            right_concept_type,
                            right_concept_id,
                        ),
                    )
                    count += 1

        self.conn.commit()
        return count

    def delete_associations(self, concept_id: str) -> int:
        """Delete all associations where this concept is involved."""
        with self.conn.cursor() as cur:
            cur.execute(
                f"""
                DELETE FROM {ASSOCIATIONS_TABLE}
                WHERE left_concept_id = %s OR right_concept_id = %s
                """,
                (concept_id, concept_id),
            )
            deleted = cur.rowcount
        self.conn.commit()
        return deleted

    def search_similar(
        self,
        embedding: list[float],
        limit: int = 10,
        concept_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search for similar embeddings using pgvector."""
        with self.conn.cursor() as cur:
            if concept_type:
                cur.execute(
                    f"""
                    SELECT concept_type, concept_id, attribute, text_content,
                           1 - (embedding <=> %s::vector) as similarity
                    FROM {EMBEDDINGS_TABLE}
                    WHERE concept_type = %s
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                    """,
                    (embedding, concept_type, embedding, limit),
                )
            else:
                cur.execute(
                    f"""
                    SELECT concept_type, concept_id, attribute, text_content,
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
                        "concept_type": row[0],
                        "concept_id": row[1],
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
                SELECT kms_uuid, scheme, term, definition
                FROM {KMS_EMBEDDINGS_TABLE}
                WHERE kms_uuid = %s
                """,
                (kms_uuid,),
            )
            row = cur.fetchone()
            if row:
                return {
                    "kms_uuid": row[0],
                    "scheme": row[1],
                    "term": row[2],
                    "definition": row[3],
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
        """Insert or update a KMS term embedding."""
        with self.conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO {KMS_EMBEDDINGS_TABLE}
                    (kms_uuid, scheme, term, definition, embedding, updated_at)
                VALUES (%s, %s, %s, %s, %s, NOW())
                ON CONFLICT (kms_uuid) DO UPDATE SET
                    definition = EXCLUDED.definition,
                    embedding = EXCLUDED.embedding,
                    updated_at = NOW()
                RETURNING (xmax = 0) as inserted
                """,
                (kms_uuid, scheme, term, definition, embedding),
            )
            result = cur.fetchone()
            inserted = result[0] if result else False
        self.conn.commit()
        logger.info(
            "%s KMS embedding for %s/%s",
            "Inserted" if inserted else "Updated",
            scheme,
            term,
        )
        return inserted

    def upsert_concept_kms_associations(
        self,
        concept_type: str,
        concept_id: str,
        kms_uuids: list[str],
    ) -> int:
        """Link a concept to KMS terms."""
        if not kms_uuids:
            return 0

        with self.conn.cursor() as cur:
            # Delete existing KMS associations for this concept
            cur.execute(
                f"""
                DELETE FROM {KMS_ASSOCIATIONS_TABLE}
                WHERE concept_type = %s AND concept_id = %s
                """,
                (concept_type, concept_id),
            )

            # Insert new associations
            count = 0
            for kms_uuid in kms_uuids:
                cur.execute(
                    f"""
                    INSERT INTO {KMS_ASSOCIATIONS_TABLE}
                        (concept_type, concept_id, kms_uuid)
                    VALUES (%s, %s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (concept_type, concept_id, kms_uuid),
                )
                count += cur.rowcount

        self.conn.commit()
        logger.info("Created %d KMS associations for %s:%s", count, concept_type, concept_id)
        return count

    def delete_concept_kms_associations(self, concept_id: str) -> int:
        """Delete all KMS associations for a concept."""
        with self.conn.cursor() as cur:
            cur.execute(
                f"""
                DELETE FROM {KMS_ASSOCIATIONS_TABLE}
                WHERE concept_id = %s
                """,
                (concept_id,),
            )
            deleted = cur.rowcount
        self.conn.commit()
        return deleted
