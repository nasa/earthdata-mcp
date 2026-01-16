"""Base datastore abstract class for embedding storage."""

from abc import ABC, abstractmethod
from typing import Any


class EmbeddingDatastore(ABC):
    """
    Abstract base class for embedding storage.

    Implementations can use PostgreSQL, DynamoDB, Parquet, or any other storage backend.
    """

    @abstractmethod
    def upsert_chunks(
        self,
        concept_type: str,
        concept_id: str,
        chunks: list[tuple[str, str, list[float]]],  # (attribute, text_content, embedding)
    ) -> int:
        """
        Insert or update embedding chunks for a concept.

        Replaces all existing chunks for the concept with the new ones.

        Args:
            concept_type: Type of concept (collection, variable, service, citation).
            concept_id: CMR concept ID.
            chunks: List of (attribute, text_content, embedding) tuples.

        Returns:
            Number of chunks upserted.
        """
        pass

    @abstractmethod
    def delete_chunks(self, concept_id: str) -> int:
        """
        Delete all embedding chunks for a concept.

        Args:
            concept_id: CMR concept ID.

        Returns:
            Number of chunks deleted.
        """
        pass

    @abstractmethod
    def upsert_associations(
        self,
        concept_type: str,
        concept_id: str,
        associations: dict[str, list[str]],
    ) -> int:
        """
        Store concept associations.

        Args:
            concept_type: Type of the source concept.
            concept_id: CMR concept ID of the source.
            associations: Dict mapping association types to lists of concept IDs.
                         e.g., {"variables": ["V123-PROV"], "citations": ["CIT456-PROV"]}

        Returns:
            Number of associations stored.
        """
        pass

    @abstractmethod
    def delete_associations(self, concept_id: str) -> int:
        """
        Delete all associations where this concept is involved.

        Args:
            concept_id: CMR concept ID.

        Returns:
            Number of associations deleted.
        """
        pass

    def close(self) -> None:
        """
        Close any open connections or resources.

        Default implementation does nothing - connections are managed centrally
        by get_db_connection(). Override if your implementation needs cleanup.
        """
        return None

    @abstractmethod
    def search_similar(
        self,
        embedding: list[float],
        limit: int = 10,
        concept_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Search for similar embeddings.

        Args:
            embedding: Query embedding vector.
            limit: Maximum number of results.
            concept_type: Optional filter by concept type.

        Returns:
            List of matching chunks with similarity scores.
        """
        pass

    @abstractmethod
    def get_kms_embedding(self, kms_uuid: str) -> dict[str, Any] | None:
        """
        Get a KMS embedding by UUID.

        Args:
            kms_uuid: The KMS UUID.

        Returns:
            Dict with kms_uuid, scheme, term, definition, embedding, or None if not found.
        """
        pass

    @abstractmethod
    def upsert_kms_embedding(
        self,
        kms_uuid: str,
        scheme: str,
        term: str,
        definition: str | None,
        embedding: list[float],
    ) -> bool:
        """
        Insert or update a KMS term embedding.

        Args:
            kms_uuid: The KMS UUID (primary key).
            scheme: KMS scheme (platforms, instruments, sciencekeywords).
            term: The term/prefLabel.
            definition: Definition from KMS.
            embedding: Embedding vector.

        Returns:
            True if inserted, False if updated.
        """
        pass

    @abstractmethod
    def upsert_concept_kms_associations(
        self,
        concept_type: str,
        concept_id: str,
        kms_uuids: list[str],
    ) -> int:
        """
        Link a concept to KMS terms.

        Args:
            concept_type: Type of concept (collection, variable, citation).
            concept_id: CMR concept ID.
            kms_uuids: List of KMS UUIDs to associate.

        Returns:
            Number of associations created.
        """
        pass

    @abstractmethod
    def delete_concept_kms_associations(self, concept_id: str) -> int:
        """
        Delete all KMS associations for a concept.

        Args:
            concept_id: CMR concept ID.

        Returns:
            Number of associations deleted.
        """
        pass
