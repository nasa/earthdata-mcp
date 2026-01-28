"""
Output models for discover_data orchestrator tool.

Defines the structure of discovery results including matched collections,
clarifying questions for disambiguation, and search context.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class DiscoveryStatus(str, Enum):
    """Status of the discovery operation."""

    COLLECTIONS_FOUND = "collections_found"
    DISAMBIGUATION_NEEDED = "disambiguation_needed"
    INDIRECT_MATCHES = "indirect_matches"
    REFINEMENT_SUGGESTED = "refinement_suggested"
    NO_RESULTS = "no_results"
    ERROR = "error"


class ResolutionInfo(BaseModel):
    """Temporal and spatial resolution information for a collection."""

    temporal_resolution: str | None = Field(
        None, description="Temporal resolution (e.g., 'Daily', 'Monthly', '8 Day')"
    )
    temporal_resolution_value: float | None = Field(
        None, description="Temporal resolution as numeric value in days for comparison"
    )
    spatial_resolution: str | None = Field(
        None, description="Spatial resolution (e.g., '250m', '1km', '0.25 degree')"
    )
    spatial_resolution_value: float | None = Field(
        None, description="Spatial resolution as numeric value in meters for comparison"
    )


class TemporalCoverage(BaseModel):
    """Temporal coverage of a collection."""

    start_date: datetime | None = Field(None, description="Start of data coverage")
    end_date: datetime | None = Field(None, description="End of data coverage (None if ongoing)")
    is_ongoing: bool = Field(
        default=False, description="Whether the collection is still being updated"
    )


class CollectionMatch(BaseModel):
    """A matched collection with metadata and relevance info."""

    concept_id: str = Field(..., description="CMR concept ID")
    title: str = Field(..., description="Collection title")
    abstract: str | None = Field(None, description="Collection description/abstract")

    similarity_score: float = Field(
        ..., ge=0.0, le=1.0, description="Semantic similarity score (0-1)"
    )
    match_type: str = Field(
        ...,
        description="How this collection was found: 'direct', 'via_citation', "
        "'via_variable', 'via_science_keyword', 'via_instrument', 'via_platform'",
    )
    matched_attribute: str | None = Field(
        None, description="Which attribute matched (title, abstract, etc.)"
    )

    resolution: ResolutionInfo | None = Field(
        None, description="Resolution information for disambiguation"
    )
    temporal_coverage: TemporalCoverage | None = Field(
        None, description="Temporal coverage of the collection"
    )

    platforms: list[str] = Field(
        default_factory=list, description="Platform names (e.g., Terra, Aqua)"
    )
    instruments: list[str] = Field(
        default_factory=list, description="Instrument names (e.g., MODIS, ASTER)"
    )

    related_entity_id: str | None = Field(
        None,
        description="If indirect match, the ID of the entity that linked to this collection",
    )
    related_entity_text: str | None = Field(
        None, description="The text content of the related entity"
    )


class ClarifyingQuestion(BaseModel):
    """A question to help the user refine their search."""

    question_id: str | None = Field(None, description="Unique identifier for this question")
    question_text: str | None = Field(None, description="The question to present to the user")
    question_type: str | None = Field(
        None,
        description="Type: 'resolution_preference', 'temporal_scope', "
        "'spatial_scope', 'platform_preference', 'source_explanation', "
        "'data_type_preference', 'instrument_preference', 'variable_preference'",
    )
    options: list[str] = Field(
        default_factory=list, description="Available options for the user to choose from"
    )
    explanations: dict[str, str] | None = Field(
        None,
        description="Optional explanations for each option (from KMS definitions). "
        "Keys are option values, values are explanation text.",
    )
    recommendation: str | None = Field(
        None,
        description="Suggested choice based on user's query context, if applicable",
    )
    related_collection_ids: list[str] = Field(
        default_factory=list,
        description="Collection IDs this question helps disambiguate",
    )


class ExtractedConstraints(BaseModel):
    """Constraints extracted from the natural language query."""

    temporal_start: datetime | None = Field(None, description="Extracted start date")
    temporal_end: datetime | None = Field(None, description="Extracted end date")
    temporal_reasoning: str | None = Field(None, description="Explanation of temporal extraction")

    spatial_location: str | None = Field(None, description="Original location text from query")
    spatial_wkt: str | None = Field(None, description="WKT geometry for the spatial area")

    extraction_notes: list[str] = Field(
        default_factory=list, description="Notes about the extraction process"
    )


class DiscoverDataOutput(BaseModel):
    """
    Output model for the discover_data orchestrator.

    Provides discovery results with support for clarifying questions
    and iterative refinement.
    """

    status: DiscoveryStatus = Field(..., description="Status of the discovery operation")

    collections: list[CollectionMatch] = Field(
        default_factory=list, description="Matched collections"
    )
    total_found: int = Field(default=0, description="Total number of matches found")

    clarifying_questions: list[ClarifyingQuestion] = Field(
        default_factory=list, description="Questions to help refine the search"
    )

    extracted_constraints: ExtractedConstraints | None = Field(
        None, description="Constraints extracted from the query"
    )

    search_context: dict = Field(
        default_factory=dict,
        description="Serialized SearchContext for follow-up queries",
    )

    error_message: str | None = Field(None, description="Error message if status is ERROR")

    search_strategy: str | None = Field(None, description="Description of the search strategy used")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "status": "collections_found",
                    "collections": [
                        {
                            "concept_id": "C1234567890-PROVIDER",
                            "title": "MODIS/Terra Sea Surface Temperature Daily L2",
                            "similarity_score": 0.92,
                            "match_type": "direct",
                            "matched_attribute": "abstract",
                            "resolution": {
                                "temporal_resolution": "Daily",
                                "spatial_resolution": "1km",
                            },
                            "platforms": ["Terra"],
                            "instruments": ["MODIS"],
                        }
                    ],
                    "total_found": 1,
                    "clarifying_questions": [],
                    "extracted_constraints": {
                        "temporal_start": "2015-01-01T00:00:00Z",
                        "temporal_end": "2016-12-31T23:59:59Z",
                        "spatial_location": "Pacific Ocean",
                        "spatial_wkt": "POLYGON((...))...",
                    },
                },
                {
                    "status": "disambiguation_needed",
                    "collections": [],
                    "total_found": 4,
                    "clarifying_questions": [
                        {
                            "question_id": "temporal_res_123",
                            "question_text": "Multiple MODIS SST products found with different resolutions. Which do you prefer?",
                            "question_type": "resolution_preference",
                            "options": ["Daily", "8-Day", "Monthly"],
                            "explanations": None,
                            "recommendation": None,
                            "related_collection_ids": ["C123...", "C456...", "C789..."],
                        }
                    ],
                },
            ]
        }
    )
