"""
Input models for discover_data orchestrator tool.

Defines the input structure for natural language earth data discovery queries,
including optional constraints and context for iterative refinement.
"""

from pydantic import BaseModel, Field

from tools.models.constraints import SpatialConstraint, TemporalConstraint


class SearchContext(BaseModel):
    """
    Preserved context from previous search iteration.

    Allows the orchestrator to continue from where it left off
    without re-extracting constraints.
    """

    temporal: TemporalConstraint | None = Field(
        None, description="Previously extracted temporal constraint"
    )
    spatial: SpatialConstraint | None = Field(
        None, description="Previously extracted spatial constraint"
    )
    previous_collection_ids: list[str] = Field(
        default_factory=list, description="Collection IDs from previous search"
    )
    user_refinements: dict[str, str] = Field(
        default_factory=dict,
        description="User's answers to clarifying questions (question_id -> selected option)",
    )
    search_iteration: int = Field(default=0, description="Number of search iterations performed")


class DiscoverDataInput(BaseModel):
    """
    Input model for the discover_data orchestrator.

    Accepts natural language queries about earth science data,
    with optional explicit constraints and context for iterative refinement.

    **Constraint Priority:** Explicit constraints (temporal_constraint, spatial_constraint)
    take precedence over extraction from the query text.
    """

    query: str = Field(
        ...,
        description="Natural language query describing the earth science data needed. "
        "Can include topic, location, time period, instrument, or phenomenon.",
        examples=[
            "Sea surface temperature data for the Pacific Ocean during El Nino 2015-2016",
            "MODIS vegetation index for California fire season 2020",
            "High resolution precipitation data for monsoon season in India",
        ],
    )

    temporal_constraint: TemporalConstraint | None = Field(
        None,
        description="Explicit temporal constraint. If provided, skips temporal extraction from query.",
    )

    spatial_constraint: SpatialConstraint | None = Field(
        None,
        description="Explicit spatial constraint. If provided, skips spatial extraction from query.",
    )

    previous_context: SearchContext | None = Field(
        None,
        description="Context from previous search iteration for refinement.",
    )

    max_results: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of collections to return.",
    )

    similarity_threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Minimum combined score for collection matches. "
        "Collections are scored based on direct similarity and indirect signals "
        "from related entities (variables, instruments, citations, etc.).",
    )
