"""Input and output models for the get_services MCP tool."""

from typing import Annotated, Any

from pydantic import BaseModel, Field

from models.tools.cmr_search import BaseCmrSearchOutput

CollectionConceptIdParam = Annotated[
    str,
    Field(
        description=(
            "Parent collection concept ID (format: C<number>-<PROVIDER>, "
            "e.g., C2723758340-GES_DISC). Required to scope service search."
        )
    ),
]


class ServiceResult(BaseModel):
    """Minimal service result for direct CMR-backed retrieval."""

    concept_id: str = Field(..., description="CMR service concept ID")
    name: str | None = Field(None, description="The name of the service")
    long_name: str | None = Field(None, description="The long name of the service")
    type: str | None = Field(None, description="The type of the service")
    version: str | None = Field(None, description="The edition or version of the service")
    description: str | None = Field(None, description="A brief description of the service")
    url: dict[str, Any] | None = Field(None, description="Primary endpoint URL information")
    related_urls: list[dict[str, Any]] | None = Field(
        None, description="Documentation, guides, or other related links"
    )
    access_constraints: dict[str, Any] | str | None = Field(
        None, description="Authentication or authorization requirements"
    )
    use_constraints: dict[str, Any] | str | None = Field(
        None, description="Legal restrictions or usage limits"
    )
    service_options: dict[str, Any] | None = Field(
        None, description="Subset types, supported projections, output formats"
    )
    operation_metadata: list[dict[str, Any]] | None = Field(
        None, description="Operation names and distributed computing platform"
    )


class GetServicesInput(BaseModel):
    """Input model for get_services."""

    collection_concept_id: CollectionConceptIdParam


class GetServicesOutput(BaseCmrSearchOutput):
    """Output model for get_services."""

    services: list[ServiceResult] = Field(
        default_factory=list, description="Normalized service results mapped from UMM-S"
    )
