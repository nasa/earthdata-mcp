"""
Extraction models for temporal and spatial constraint parsing.
"""

import hashlib
from datetime import datetime

from pydantic import BaseModel, computed_field


class ParsedTemporalExtraction(BaseModel):
    """Parsed temporal information extracted by LLM."""

    start_date: datetime | None = None
    end_date: datetime | None = None
    reasoning: str | None = None


class ParsedSpatialExtraction(BaseModel):
    """Parsed spatial information extracted by LLM with computed cache key."""

    location_name: str | None = None
    location_with_context: str | None = None
    reasoning: str | None = None

    @computed_field
    @property
    def cache_key(self) -> str | None:
        """Compute cache key from location_name."""
        if self.location_name:
            normalized = self.location_name.lower().strip()
            return f"geocode:{hashlib.sha256(normalized.encode()).hexdigest()}"
        return None
