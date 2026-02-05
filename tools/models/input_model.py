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

    Include this on follow-up queries to keep previously extracted
    temporal/spatial constraints and any user refinements.

    If the user changes temporal or spatial constraints, set the corresponding
    search_context.temporal or search_context.spatial field to null/None so that
    extract_constraints will re-extract from the new query. Keeping prior values
    prevents re-extraction.

    Reusing prior context avoids re-extraction and can reduce latency.
    """

    temporal: TemporalConstraint | None = Field(
        None,
        description=(
            "Previously extracted temporal constraint. Include to keep the same time range "
            "and avoid re-extraction."
        ),
    )
    spatial: SpatialConstraint | None = Field(
        None,
        description=(
            "Previously extracted spatial constraint. Include to keep the same location/geometry "
            "and avoid re-extraction."
        ),
    )
    previous_collection_ids: list[str] = Field(
        default_factory=list, description="Collection IDs from previous search"
    )
    user_refinements: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "User's answers to clarifying questions (question_id -> selected option). "
            "Include when the user picks a disambiguation option."
        ),
    )
    search_iteration: int = Field(default=0, description="Number of search iterations performed")


class DiscoverDataInput(BaseModel):
    """
    Input for natural language data discovery. Required: query. Optional: config (max_results,
    similarity_threshold) and search_context for follow-up queries.
    """

    # Required
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

    # Config
    max_results: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of collections to return.",
    )

    similarity_threshold: float = Field(
        default=0.35,
        ge=0.0,
        le=1.0,
        description=(
            "Minimum combined score for collection matches (0.0-1.0). "
            "Collections are scored based on embedding similarity and indirect signals from related entities. "
            "Lower threshold returns more results but may include less relevant collections. "
            "Default 0.35 balances recall and precision based on typical embedding score distributions."
        ),
    )

    # Search context (opaque passthrough - same name in input and output)
    search_context: SearchContext | None = Field(
        None,
        description=(
            "For follow-up queries: Pass back the 'search_context' object from the prior response. "
            "Callers may modify specific fields: set temporal or spatial to null to force re-extraction "
            "when the user changes those constraints, or update user_refinements to answer clarifying questions. "
            "Otherwise, treat this as an opaque object - do not stringify or manually reconstruct it."
        ),
    )
