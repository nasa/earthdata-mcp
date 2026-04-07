"""Input and output models for the get_tools MCP tool."""

import re
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from models.tools.cmr_search import BaseCmrSearchOutput

CollectionConceptIdParam = Annotated[
    str,
    Field(
        description=(
            "Parent collection concept ID (format: C<number>-<PROVIDER>, "
            "e.g., C2723758340-GES_DISC). Required to scope tool search."
        ),
    ),
]


class ToolResult(BaseModel):
    """Normalized tool result for direct CMR-backed retrieval."""

    access_constraints: str | None = Field(None, description="Constraints for accessing the tool")
    concept_id: str = Field(..., description="CMR tool concept ID")
    description: str | None = Field(None, description="A brief description of the tool")
    doi: str | None = Field(None, description="Digital Object Identifier of the tool")
    long_name: str | None = Field(None, description="The long name of the tool")
    name: str | None = Field(None, description="The name of the tool")
    native_id: str | None = Field(None, description="The native ID of the tool record")
    organizations: list[dict[str, Any]] | None = Field(
        None, description="Organizations responsible for the tool"
    )
    potential_action: dict[str, Any] | None = Field(
        None, description="Smart handoff definition for parameterized deep links"
    )
    provider_id: str | None = Field(None, description="The provider ID of the tool")
    quality: dict[str, Any] | None = Field(None, description="Quality information about the tool")
    related_urls: list[dict[str, Any]] | None = Field(
        None, description="Documentation, guides, or other related links"
    )
    revision_id: int | None = Field(None, description="The revision ID of the tool metadata")
    supported_browsers: list[dict[str, Any]] | None = Field(
        None, description="Browsers and versions supported by the tool"
    )
    supported_input_formats: list[str] | None = Field(
        None, description="List of input format names supported by the tool"
    )
    supported_operating_systems: list[dict[str, Any]] | None = Field(
        None, description="Operating systems and versions supported by the tool"
    )
    supported_output_formats: list[str] | None = Field(
        None, description="List of output format names supported by the tool"
    )
    supported_software_languages: list[dict[str, Any]] | None = Field(
        None, description="Programming languages and versions supported by the tool"
    )
    tool_keywords: list[dict[str, Any]] | None = Field(
        None, description="Earth science keywords representative of the tool"
    )
    type: str | None = Field(
        None,
        description="The type of the tool (e.g., Downloadable Tool, Web User Interface, Web Portal, Model)",
    )
    url: dict[str, Any] | None = Field(None, description="Primary URL for accessing the tool")
    use_constraints: dict[str, Any] | None = Field(
        None, description="Restrictions or limitations on using the tool"
    )
    version: str | None = Field(None, description="The edition or version of the tool")


class GetToolsInput(BaseModel):
    """Input model for get_tools."""

    model_config = ConfigDict(extra="forbid")

    collection_concept_id: CollectionConceptIdParam

    @field_validator("collection_concept_id")
    @classmethod
    def validate_format(cls, v: str) -> str:
        if not re.match(r"^C\d+-[A-Za-z0-9_]+$", v):
            raise ValueError(
                "Invalid collection concept ID format. "
                "Must match C<number>-<PROVIDER> (e.g., C2723758340-GES_DISC)."
            )
        return v


class GetToolsOutput(BaseCmrSearchOutput):
    """Output model for get_tools."""

    tools: list[ToolResult] = Field(
        default_factory=list, description="Normalized tool results mapped from UMM-T"
    )
