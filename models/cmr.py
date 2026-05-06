"""Centralized Pydantic models for the embedding pipeline."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ConceptType(str, Enum):
    """Valid concept types in the CMR system."""

    COLLECTION = "collection"
    VARIABLE = "variable"
    CITATION = "citation"


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

    kms_terms: list[KMSTerm] = Field(default_factory=list)


@dataclass
class CollectionData:
    """Data for upserting a collection to the collections table."""

    metadata: dict[str, Any]
    enriched_metadata: dict[str, Any]
    temporal_start: datetime | None
    temporal_end: datetime | None
    is_ongoing: bool
    spatial_wkt: str | None
    is_global: bool
