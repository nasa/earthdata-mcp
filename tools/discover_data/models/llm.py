"""
LLM-based extraction models.

Defines Pydantic models and dataclasses used for structured extraction of
temporal and spatial information from natural language queries.
"""

import hashlib
from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel


class TemporalRangeOutput(BaseModel):
    """Output model for temporal range extraction from LLM."""

    start_date: datetime | None = None
    end_date: datetime | None = None
    reasoning: str | None = None


class SpatialExtractionOutput(BaseModel):
    """Output model for spatial extraction from LLM."""

    location_name: str | None = None
    location_with_context: str | None = None
    reasoning: str | None = None


@dataclass
class SpatialExtractionResult:
    """Result of LLM-based spatial extraction with computed cache key."""

    location_name: str | None
    location_with_context: str | None
    reasoning: str | None
    cache_key: str | None = None

    def __post_init__(self) -> None:
        """Compute cache key from location name."""
        if self.location_name:
            normalized = self.location_name.lower().strip()
            self.cache_key = f"geocode:{hashlib.sha256(normalized.encode()).hexdigest()}"
