"""Input and output models for the get_capabilities MCP tool.

Wraps the NASA Harmony `/capabilities` endpoint, which returns the set of
Harmony transformation capabilities (subsetting, reprojection, averaging,
concatenation, output formats, applicable services, and variables) for a
single CMR collection.

Reference:
- https://github.com/nasa/harmony/blob/main/services/harmony/app/markdown/capabilities.md
- https://github.com/nasa/harmony/blob/main/services/harmony/app/frontends/capabilities.ts

This models the version 3 response format. The capabilities version is
pinned server-side (hardcoded to '3' on the request to Harmony) so it stays
in sync with these models; it is intentionally not exposed as a tool input.
"""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator
from models.tools.harmony import BaseHarmonyToolOutput

CollectionIdParam = Annotated[
    str | None,
    Field(
        description=(
            "Concept ID of the collection to retrieve capabilities for "
            "(format: C<number>-<PROVIDER>, e.g., C1234567890-PROVIDER). "
            "Exactly one of collection_id or short_name must be provided."
        )
    ),
]

ShortNameParam = Annotated[
    str | None,
    Field(
        description=(
            "Short name of the collection to retrieve capabilities for. "
            "Exactly one of collection_id or short_name must be provided. "
            "If multiple collections share the short name, Harmony prefers "
            "the one configured for use in Harmony."
        )
    ),
]


class Projection(BaseModel):
    """A supported output reprojection."""

    name: str | None = Field(None, description="Human-readable projection name")
    crs: str = Field(
        ...,
        description=(
            "Coordinate reference system authority code for the projection "
            "(e.g., 'EPSG:4326'). Pass this value as the outputCRS parameter "
            "in a Harmony transformation request."
        ),
    )


class OutputFormat(BaseModel):
    """A supported output format."""

    name: str = Field(..., description="Human-readable output format name")
    mime_type: str = Field(
        ..., alias="mimeType", description="MIME type of the output format"
    )

    model_config = ConfigDict(populate_by_name=True)


class SubsettingCapabilities(BaseModel):
    """Subsetting capabilities supported by any applicable service."""

    bbox: bool = Field(False, description="True if bounding box subsetting is supported")
    dimension: bool = Field(False, description="True if dimension subsetting is supported")
    shape: bool = Field(False, description="True if shape (polygon) subsetting is supported")
    temporal: bool = Field(False, description="True if temporal subsetting is supported")
    variable: bool = Field(False, description="True if variable subsetting is supported")


class ReprojectionCapabilities(BaseModel):
    """Reprojection capabilities supported by any applicable service."""

    supported: bool = Field(False, description="True if reprojection is supported")
    supported_projections: list[Projection] = Field(
        default_factory=list,
        alias="supportedProjections",
        description="Output projections supported across applicable services",
    )
    interpolation_methods: list[str] = Field(
        default_factory=list,
        alias="interpolationMethods",
        description="Interpolation methods supported for resampling during reprojection",
    )

    model_config = ConfigDict(populate_by_name=True)


class AveragingCapabilities(BaseModel):
    """Averaging capabilities supported by any applicable service."""

    time: bool = Field(False, description="True if time averaging is supported")
    area: bool = Field(False, description="True if area averaging is supported")


class ServiceCapabilitiesSummary(BaseModel):
    """Collection-level summary of capabilities across all applicable services.

    Some capabilities cannot be used together; check the per-service entries
    in `services` to determine which combinations a given service supports.
    """

    subsetting: SubsettingCapabilities = Field(default_factory=SubsettingCapabilities)
    reprojection: ReprojectionCapabilities = Field(default_factory=ReprojectionCapabilities)
    averaging: AveragingCapabilities = Field(default_factory=AveragingCapabilities)
    concatenation: bool = Field(False, description="True if concatenation is supported")
    output_formats: list[OutputFormat] = Field(
        default_factory=list,
        alias="outputFormats",
        description="Output formats supported across all applicable services",
    )

    model_config = ConfigDict(populate_by_name=True)


class ServiceInfo(BaseModel):
    """A Harmony service applicable to the collection."""

    name: str = Field(..., description="Name of the Harmony service")
    href: str | None = Field(
        None, description="Reference URL to the service's UMM-S record in CMR"
    )
    capabilities: ServiceCapabilitiesSummary = Field(
        ..., description="Capabilities supported by this specific service"
    )


class ScienceKeyword(BaseModel):
    """A GCMD science keyword associated with a variable."""

    category: str | None = Field(None, alias="Category")
    topic: str | None = Field(None, alias="Topic")
    term: str | None = Field(None, alias="Term")
    variable_level_1: str | None = Field(None, alias="VariableLevel1")
    variable_level_2: str | None = Field(None, alias="VariableLevel2")
    variable_level_3: str | None = Field(None, alias="VariableLevel3")
    detailed_variable: str | None = Field(None, alias="DetailedVariable")

    model_config = ConfigDict(populate_by_name=True)


class VariableInfo(BaseModel):
    """A variable associated with the collection."""

    name: str = Field(..., description="Variable short name")
    long_name: str | None = Field(
        None, alias="longName", description="Variable long/display name"
    )
    href: str | None = Field(
        None, description="Reference URL to the variable's UMM-Var record in CMR"
    )
    units: str | None = Field(None, description="Units of measurement for the variable")
    science_keywords: list[ScienceKeyword] = Field(
        default_factory=list,
        alias="scienceKeywords",
        description="GCMD science keywords describing the variable",
    )

    model_config = ConfigDict(populate_by_name=True)


class GetCollectionCapabilitiesInput(BaseModel):
    """Input model for get_capabilities."""

    model_config = ConfigDict(extra="forbid")

    collection_id: CollectionIdParam = None
    short_name: ShortNameParam = None

    @model_validator(mode="after")
    def _check_collection_identifier(self) -> "GetCapabilitiesInput":
        if not self.collection_id and not self.short_name:
            raise ValueError("Must specify either collection_id or short_name")
        if self.collection_id and self.short_name:
            raise ValueError(
                "Must specify only one of collection_id or short_name, not both"
            )
        return self


class GetCollectionCapabilitiesOutput(BaseHarmonyToolOutput):
    """Output model for get_capabilities (version 3 response format)."""

    concept_id: str | None  = Field(default=None, alias="conceptId", description="Concept ID of the collection")
    short_name: str | None  = Field(default=None, alias="shortName", description="Short name of the collection")
    summary: ServiceCapabilitiesSummary | None  = Field(
        default=None,
        description=(
            "Summary of Harmony capabilities available for the collection: "
            "subsetting, reprojection, averaging, concatenation, and output formats"
        ),
    )
    services: list[ServiceInfo] = Field(
        default_factory=list,
        description="Harmony services applicable to the collection and their capabilities",
    )
    variables: list[VariableInfo] = Field(
        default_factory=list, description="Variables associated with the collection"
    )
    capabilities_version: str | None  = Field(
        default=None,
        alias="capabilitiesVersion",
        description="Version identifier of this capabilities response format",
    )

    model_config = ConfigDict(populate_by_name=True)