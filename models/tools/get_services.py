"""Input and output models for the get_services MCP tool."""

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from models.pagination import CursorParam, FieldsParam, LimitParam
from models.tools.cmr_search import BaseCmrSearchOutput


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
    service_keywords: list[dict[str, Any]] | None = Field(
        None, description="Controlled vocabulary for service capability"
    )
    service_options: dict[str, Any] | None = Field(
        None, description="Subset types, supported projections, output formats"
    )
    service_organizations: list[dict[str, Any]] | None = Field(
        None, description="Organizations that run the service endpoint"
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

    collection_concept_id: str | None = None
    keyword: str | None = None
    type: str | None = None
    limit: LimitParam = 10
    cursor: CursorParam = None
    fields: FieldsParam

    @model_validator(mode="after")
    def validate_inputs(self) -> "GetServicesInput":
        """Validate that at least one search parameter is provided and format is correct."""
        if self.collection_concept_id is None and self.keyword is None and self.type is None:
            raise ValueError(
                "At least one of collection_concept_id, keyword, or type must be provided."
            )
        if self.collection_concept_id is not None and not re.match(
            r"^C\d+-[A-Za-z0-9_]+$", self.collection_concept_id
        ):
            raise ValueError(
                "Invalid collection concept ID format. "
                "Must match C<number>-<PROVIDER> (e.g., C2723758340-GES_DISC)."
            )
        return self


class GetServicesOutput(BaseCmrSearchOutput):
    """Output model for get_services."""

    next_cursor: str | None = Field(default=None, description="Pagination token for the next page")
    services: list[ServiceResult] = Field(
        default_factory=list, description="Normalized service results mapped from UMM-S"
    )
