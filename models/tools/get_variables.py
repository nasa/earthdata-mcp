"""Input and output models for the get_variables MCP tool."""

from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from models.tools.cmr_search import BaseCmrSearchOutput


class VariableResult(BaseModel):
    """Normalized variable result for direct CMR-backed retrieval."""

    concept_id: str = Field(..., description="CMR variable concept ID")
    name: str | None = Field(None, description="The short name of the variable")
    long_name: str | None = Field(None, description="The long name of the variable")
    definition: str | None = Field(None, description="The definition of the variable")
    data_type: str | None = Field(None, description="The data type of the variable")
    units: str | None = Field(None, description="The units of the variable")
    scale: float | None = Field(None, description="The scale factor for the variable data")
    offset: float | None = Field(None, description="The offset for the variable data")
    fill_values: list[dict[str, Any]] | None = Field(
        None, description="Fill values used for missing or invalid data"
    )
    valid_ranges: list[dict[str, Any]] | None = Field(
        None, description="Valid data ranges for the variable"
    )
    dimensions: list[dict[str, Any]] | None = Field(
        None, description="Dimensions associated with the variable"
    )
    standard_name: str | None = Field(None, description="The CF Standard Name of the variable")
    science_keywords: list[dict[str, Any]] | None = Field(
        None, description="GCMD Science Keywords hierarchy"
    )
    variable_type: str | None = Field(
        None, description="Type of variable (e.g., SCIENCE_VARIABLE, COORDINATE)"
    )
    variable_sub_type: str | None = Field(None, description="Sub-type of variable")
    sets: list[dict[str, Any]] | None = Field(
        None, description="Logical groupings for the variable"
    )
    measurement_identifiers: list[dict[str, Any]] | None = Field(
        None, description="Measurement context and provenance"
    )
    sampling_identifiers: list[dict[str, Any]] | None = Field(
        None, description="Sampling method context"
    )
    related_urls: list[dict[str, Any]] | None = Field(
        None, description="URLs specific to the variable"
    )


class GetVariablesInput(BaseModel):
    """Input model for get_variables."""

    model_config = ConfigDict(extra="forbid")

    collection_concept_id: Annotated[
        str | None,
        Field(
            None,
            description="The CMR concept ID of the collection to find variables for (e.g., 'C12345-PROV').",
        ),
    ]
    keyword: Annotated[
        str | None,
        Field(
            None,
            description="A free-text search keyword to find variables.",
        ),
    ]

    @model_validator(mode="after")
    def check_at_least_one_identifier(self) -> "GetVariablesInput":
        """Ensure either a collection_concept_id or keyword is provided."""
        if not self.collection_concept_id and not self.keyword:
            raise ValueError("Must provide either a collection_concept_id or a keyword")
        return self


class GetVariablesOutput(BaseCmrSearchOutput):
    """Output model for get_variables."""

    variables: list[VariableResult] = Field(
        default_factory=list, description="Normalized variable results mapped from UMM-V"
    )
