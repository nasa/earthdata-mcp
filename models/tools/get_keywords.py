"""Input and output models for the get_keywords MCP tool."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from models.tools.cmr_search import BaseCmrSearchOutput


class KeywordResult(BaseModel):
    """A single matching KMS keyword result."""

    uuid: str = Field(..., description="The unique UUID of the KMS concept")
    prefLabel: str = Field(..., description="The preferred label of the KMS concept")
    scheme: dict[str, str] = Field(..., description="The scheme the concept belongs to")
    definition: str | None = Field(
        None, description="The primary definition of the concept, if available"
    )


class GetKeywordsInput(BaseModel):
    """Input model for get_keywords."""

    model_config = ConfigDict(extra="forbid")

    query: Annotated[
        str,
        Field(
            ...,
            min_length=1,
            pattern=r"\S",
            description="The term to search for across KMS schemes (e.g. 'moisture').",
        ),
    ]
    scheme: Annotated[
        str | None,
        Field(
            None,
            description=(
                "Optional. A single KMS scheme to narrow the search (e.g., 'sciencekeywords', "
                "'platforms', 'instruments', 'projects', 'providers', 'locations'). "
                "If omitted, searches across all schemes globally. "
                "A complete list of valid scheme names can be fetched from "
                "https://cmr.earthdata.nasa.gov/kms/concept_schemes"
            ),
        ),
    ]


class GetKeywordsOutput(BaseCmrSearchOutput):
    """Output model for get_keywords."""

    keywords: list[KeywordResult] = Field(
        default_factory=list, description="List of matched KMS terms"
    )
