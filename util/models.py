"""Centralized Pydantic models for the embedding pipeline."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ConceptMessage(BaseModel):
    """Message from the ingest queue describing a CMR concept event."""

    model_config = ConfigDict(populate_by_name=True)

    action: Literal["concept-update", "concept-delete"]
    concept_type: Literal["collection", "variable", "citation"] = Field(alias="concept-type")
    concept_id: str = Field(alias="concept-id")
    revision_id: int = Field(alias="revision-id")


class EmbeddingChunk(BaseModel):
    """
    A piece of text extracted from a CMR concept, ready to be embedded.

    We split concepts into chunks by attribute (title, abstract, etc.) for:
    - More precise similarity matching during search
    - Better RAG retrieval (return specific relevant text, not whole record)
    """

    concept_type: str
    concept_id: str
    attribute: str
    text_content: str


class KMSTerm(BaseModel):
    """
    A term from the Keyword Management System.

    During extraction, only term and scheme are set. After KMS lookup,
    uuid and definition are populated.
    """

    term: str
    scheme: str
    uuid: str | None = None
    definition: str | None = None


class ExtractionResult(BaseModel):
    """Result of extracting embeddable data from a CMR concept."""

    chunks: list[EmbeddingChunk] = Field(default_factory=list)
    kms_terms: list[KMSTerm] = Field(default_factory=list)
