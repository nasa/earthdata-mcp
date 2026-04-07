"""Input and output models for the get_services MCP tool."""

import re
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from models.tools.cmr_search import BaseCmrSearchOutput

CollectionConceptIdParam = Annotated[
    str,
    Field(
        description=(
            "Parent collection concept ID (format: C<number>-<PROVIDER>, "
            "e.g., C2723758340-GES_DISC). Required to scope service search."
        ),
    ),
]


class ServiceResult(BaseModel):
    """Minimal service result for direct CMR-backed retrieval."""

    access_constraints: dict[str, Any] | str | None = Field(
        None, description="Authentication or authorization requirements"
    )
    concept_id: str = Field(..., description="CMR service concept ID")
    description: str | None = Field(None, description="A brief description of the service")
    long_name: str | None = Field(None, description="The long name of the service")
    name: str | None = Field(None, description="The name of the service")
    native_id: str | None = Field(None, description="The native ID of the service record")
    operation_metadata: list[dict[str, Any]] | None = Field(
        None, description="Operation names and distributed computing platform"
    )
    provider_id: str | None = Field(None, description="The provider ID of the service")
    related_urls: list[dict[str, Any]] | None = Field(
        None, description="Documentation, guides, or other related links"
    )
    revision_id: int | None = Field(None, description="The revision ID of the service metadata")
    service_options: dict[str, Any] | None = Field(
        None, description="Subset types, supported projections, output formats"
    )
    type: str | None = Field(None, description="The type of the service")
    url: dict[str, Any] | None = Field(None, description="Primary endpoint URL information")
    use_constraints: dict[str, Any] | str | None = Field(
        None, description="Legal restrictions or usage limits"
    )
    version: str | None = Field(None, description="The edition or version of the service")


class GetServicesInput(BaseModel):
    """Input model for get_services."""

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


class GetServicesOutput(BaseCmrSearchOutput):
    """Output model for get_services."""

    services: list[ServiceResult] = Field(
        default_factory=list, description="Normalized service results mapped from UMM-S"
    )
