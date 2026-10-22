"""Input and output models for the get_events MCP tool."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from models.pagination import LimitParam
from models.tools.cmr_search import BaseToolOutput


class LayerResult(BaseModel):
    """A single EONET layer object."""

    name: str = Field(..., description="The EONET-provided name of the layer")
    serviceUrl: str | None = Field(None, description="The link to the provider of the layer")
    serviceTypeId: str | None = Field(None, description="Type and version of provider's data")
    parameters: list | None = Field(None, description="Query parameters required for the provider's request URL")


class CategoryResult(BaseModel):
    """A single EONET category object."""

    id: int = Field(..., description="The unique ID of the category")
    title: str = Field("", description="The EONET-provided title of the category")
    link: str | None = Field(None, description="The API endpoint URL for the category")
    description: str | None = Field(
            None, description="The primary description of the category, if available"
        )
    layers: list[LayerResult] | None = Field(None, description="EONET endpoint URL for the category's layers")


class EventResult(BaseModel):
    """A single EONET event object."""

    id: str = Field(..., description="The unique ID of the event")
    title: str | None = Field(None, description="The EONET-provided title of the event")
    description: str | None = Field(
        None, description="The primary description of the event, if available"
    )
    link: str | None = Field(None, description="The API endpoint URL for the event")
    closed: str | None = Field(
        None, description="Indicates if the event is closed, and if so, when it closed"
    )
    categories: list[CategoryResult] | None = Field(
        None, description="The list of categories to which the event belongs"
    )
    sources: list | None = Field(
        None, description="The list of sources that reference the event"
    )
    geometry: list | None = Field(
        None, description="The list of locations/times associated with the event"
    )


class GeoJSONResult(BaseModel):
    """A single EONET event in GeoJSON format."""
    type: str = Field(
        ..., description="The GeoJSON object's type"
    )
    properties: dict = Field(
        ..., description="GeoJSON result metadata"
    )
    geometry: dict = Field(
        ..., description="Location info and object type for the GeoJSON result"
    )


class GetEventsInput(BaseModel):
    """Input model for get_events."""

    model_config = ConfigDict(extra="forbid")

    endpoint: Annotated[
        str,
        Field(
            ...,
            pattern=r"[a-z]+/?[a-z]*?",
            description="The EONET endpoint for the API call (e.g. 'events').",
        ),
    ]
    params: Annotated[
        dict,
        Field(
            ...,
            description=(
                "Optional. A dictionary of filters to apply to the EONET API call. "
                "Detailed descriptions of each filter parameter can be found at "
                "https://eonet.gsfc.nasa.gov/docs/v3"
            ),
        ),
    ]
    limit: LimitParam = 5
    category: Annotated[
        str,
        Field(
            "",
            description="The optional category to pass to the categories or layers functions"
        )
    ]


class GetEventsOutput(BaseToolOutput):
    """Output model for get_events."""

    title: str = Field("", description="The EONET-provided title of the response")
    description: str = Field(
        "", description="Information describing what was requested, if available"
    )
    link: str = Field("", description="The API endpoint URL that was used to get the response")
    type: str = Field("", description="The type of result if GeoJSON is requested")
    events: list[EventResult] = Field(
        [], description="The list of results if an event or a category was requested"
    )
    features: list[GeoJSONResult] = Field(
        [], description="The list of results if GeoJSON was requested"
    )
    categories: list[CategoryResult] = Field(
        [], description="The list of results if layers were requested"
    )

