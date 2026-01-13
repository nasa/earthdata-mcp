"""Input model for collections embeddings queries."""

from typing import Optional
from pydantic import BaseModel, Field

from tools.temporal_ranges.output_model import TemporalRangeOutput
from tools.geospatial_embeddings.output_model import GeospatialOutput


class CollectionsEmbeddingsInput(BaseModel):
    """
    Input model for collections embeddings queries.

    Validates natural language strings for searching collections using embeddings.
    Supports optional spatial and temporal constraints.
    """

    query: str = Field(
        ...,
        description=(
            "A string of text about earth sciences to search collections with "
            "using embeddings."
        ),
    )

    spatial: Optional[GeospatialOutput] = Field(
        default=None,
        description=(
            "Optional spatial constraint from geospatial tool "
            "(contains WKT geometry)"
        ),
    )

    temporal: Optional[TemporalRangeOutput] = Field(
        default=None,
        description=(
            "Optional temporal constraint from temporal ranges tool "
            "(contains StartDate and EndDate)"
        ),
    )

    page_size: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Number of results to return per page (1-100)",
    )

    page_num: int = Field(
        default=0,
        ge=0,
        description="Page number for pagination (0-indexed)",
    )
