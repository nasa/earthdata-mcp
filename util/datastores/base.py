"""Base datastore abstract class for embedding storage."""

from abc import ABC, abstractmethod
from typing import Any

from util.models import CollectionData, ConceptType


class EmbeddingDatastore(ABC):
    """
    Abstract base class for embedding storage.

    Implementations can use PostgreSQL, DynamoDB, Parquet, or any other storage backend.
    """

    @abstractmethod
    def upsert_chunks(
        self,
        entity_type: ConceptType | str,
        external_id: str,
        chunks: list[tuple[str, str, list[float]]],  # (attribute, text_content, embedding)
    ) -> int:
        """
        Insert or update embedding chunks for an entity.

        Replaces all existing chunks for the entity with the new ones.

        Args:
            entity_type: Type of entity (collection, variable, citation, instrument, etc.).
            external_id: External identifier (concept ID or KMS UUID).
            chunks: List of (attribute, text_content, embedding) tuples.

        Returns:
            Number of chunks upserted.
        """

    @abstractmethod
    def delete_chunks(self, external_id: str) -> int:
        """
        Delete all embedding chunks for an entity.

        Args:
            external_id: External identifier.

        Returns:
            Number of chunks deleted.
        """

    @abstractmethod
    def upsert_associations(
        self,
        left_type: ConceptType | str,
        left_id: str,
        associations: dict[str, list[str]],
    ) -> int:
        """
        Store associations between entities.

        Args:
            left_type: Type of the source entity.
            left_id: External ID of the source.
            associations: Dict mapping association types to lists of IDs.
                         e.g., {"variables": ["V123-PROV"], "citations": ["CIT456-PROV"]}

        Returns:
            Number of associations stored.
        """

    @abstractmethod
    def delete_associations(self, external_id: str) -> int:
        """
        Delete all associations where this entity is involved.

        Args:
            external_id: External identifier.

        Returns:
            Number of associations deleted.
        """

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
        entity_type: ConceptType | str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Search for similar embeddings.

        Args:
            embedding: Query embedding vector.
            limit: Maximum number of results.
            entity_type: Optional filter by entity type.

        Returns:
            List of matching chunks with similarity scores.
        """

    @abstractmethod
    def get_kms_embedding(self, kms_uuid: str) -> dict[str, Any] | None:
        """
        Get a KMS embedding by UUID.

        Args:
            kms_uuid: The KMS UUID.

        Returns:
            Dict with type, external_id, attribute, text_content, embedding, or None if not found.
        """

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
            kms_uuid: The KMS UUID (used as external_id).
            scheme: KMS scheme (platforms, instruments, sciencekeywords).
            term: The term/prefLabel.
            definition: Definition from KMS.
            embedding: Embedding vector.

        Returns:
            True if inserted, False if already existed.
        """

    @abstractmethod
    def upsert_kms_associations(
        self,
        left_type: ConceptType | str,
        left_id: str,
        kms_refs: list[tuple[str, str]],  # List of (kms_uuid, scheme)
    ) -> int:
        """
        Link an entity to KMS terms.

        Args:
            left_type: Type of entity (collection, variable, citation).
            left_id: External ID.
            kms_refs: List of (kms_uuid, scheme) tuples to associate.

        Returns:
            Number of associations created.
        """

    @abstractmethod
    def delete_kms_associations(self, external_id: str) -> int:
        """
        Delete all KMS associations for an entity.

        Args:
            external_id: External identifier.

        Returns:
            Number of associations deleted.
        """

    @abstractmethod
    def upsert_collection(self, concept_id: str, data: CollectionData) -> None:
        """
        Upsert collection metadata into the collections table.

        Args:
            concept_id: CMR concept ID
            data: CollectionData containing metadata and derived fields
        """

    @abstractmethod
    def delete_collection(self, concept_id: str) -> bool:
        """
        Delete collection metadata from the collections table.

        Args:
            concept_id: CMR concept ID

        Returns:
            True if deleted, False if not found.
        """

    @abstractmethod
    def get_collections_for_entities(self, entities: list[tuple[str, str]]) -> dict[str, list[str]]:
        """
        Get all collections associated with given entities.

        Args:
            entities: List of (entity_id, entity_type) tuples

        Returns:
            Dict mapping entity_id to list of collection IDs
        """

    @abstractmethod
    def fetch_collections_by_ids(
        self,
        concept_ids: list[str],
        temporal_start: Any | None = None,
        temporal_end: Any | None = None,
        spatial_wkt: str | None = None,
    ) -> dict[str, dict[str, Any]]:
        """
        Fetch collection data for a list of concept IDs with optional filtering.

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
