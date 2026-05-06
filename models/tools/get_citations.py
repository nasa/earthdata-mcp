"""Input and output models for the get_citations MCP tool."""

import re
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from models.pagination import CursorParam, FieldsParam, LimitParam
from models.tools.cmr_search import BaseCmrSearchOutput


class CitationResult(BaseModel):
    """Normalized citation result for direct CMR-backed retrieval."""

    abstract: str | None = Field(None, description="The abstract of the citation")
    associated_collections: list[str] = Field(
        default_factory=list,
        description="CMR concept IDs of NASA datasets (collections) associated with this citation. CRITICAL: Pass these IDs to the get_collections tool to retrieve the human-readable dataset details.",
    )
    citation_metadata: dict[str, Any] | None = Field(
        None, description="Rich citation metadata including authors, publisher, year, and title"
    )
    concept_id: str = Field(..., description="CMR citation concept ID")
    identifier: str | None = Field(None, description="The primary identifier (e.g., DOI)")
    identifier_type: str | None = Field(None, description="Type of the identifier (e.g., DOI)")
    metadata_specification: dict[str, Any] | None = Field(
        None, description="Schema version of the citation metadata"
    )
    name: str | None = Field(None, description="The name or title of the citation")
    native_id: str | None = Field(None, description="The native ID of the citation record")
    provider_id: str | None = Field(None, description="The provider ID of the citation")
    related_identifiers: list[dict[str, Any]] | None = Field(
        None, description="Identifiers of related works"
    )
    resolution_authority: str | None = Field(
        None, description="Authority to resolve the identifier (e.g., https://doi.org)"
    )
    revision_id: int | None = Field(None, description="The revision ID of the citation metadata")


class GetCitationsInput(BaseModel):
    """Input model for get_citations."""

    model_config = ConfigDict(extra="forbid")

    collection_concept_id: Annotated[
        str | None,
        Field(
            None,
            description="The CMR concept ID of the collection to find citations for (e.g., 'C12345-PROV').",
        ),
    ]
    identifier: Annotated[
        str | None,
        Field(
            None,
            description="A DOI or other citation identifier used to directly look up a citation.",
        ),
    ]

    provider: str | None = Field(
        None,
        description=(
            "Optional. Filter results to citations from a specific CMR provider "
            "(e.g., 'ESDIS'). Can be combined with collection_concept_id or identifier."
        ),
    )
    limit: LimitParam = 10
    cursor: CursorParam = None
    fields: FieldsParam

    @model_validator(mode="after")
    def check_exactly_one_identifier(self) -> "GetCitationsInput":
        """Ensure exactly one of collection_concept_id or identifier is provided."""
        if self.collection_concept_id is not None and self.collection_concept_id == "":
            raise ValueError("collection_concept_id cannot be an empty string.")

        if self.identifier is not None and self.identifier == "":
            raise ValueError("identifier cannot be an empty string.")

        if (self.collection_concept_id is None) == (self.identifier is None):
            raise ValueError("Must provide exactly one of collection_concept_id or identifier.")

        # Validate format if collection_concept_id is provided
        if self.collection_concept_id and not re.match(
            r"^C\d+-[A-Za-z0-9_]+$", self.collection_concept_id
        ):
            raise ValueError(
                "Invalid collection concept ID format. "
                "Must match C<number>-<PROVIDER> (e.g., C2723758340-GES_DISC)."
            )
        return self


class GetCitationsOutput(BaseCmrSearchOutput):
    """Output model for get_citations."""

    next_cursor: str | None = Field(
        default=None, description="Pagination token for the next page; None when no more results"
    )
    citations: list[CitationResult] = Field(
        default_factory=list, description="Normalized citation results mapped from UMM-Citations"
    )
