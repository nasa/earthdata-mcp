"""Input and output models for the get_events MCP tool."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from models.pagination import LimitParam
from models.tools.cmr_search import BaseToolOutput


class EventResult(BaseModel):
    """A single EONET event object."""

    id: str = Field(..., description="The unique ID of the event")
    title: str = Field(..., description="The EONET-provided title of the event")
    description: str = Field(
        ..., description="The primary description of the event, if available"
    )
    link: str = Field(..., description="The API endpoint URL for the event")
    closed: str = Field(
        ..., description="Indicates if the event is closed, and if so, when it closed"
    )
    categories: list = Field(
        ..., description="The list of categories to which the event belongs"
    )
    sources: list = Field(
        ..., description="The list of sources that reference the event"
    )
    geometry: list = Field(
        ..., description="The list of locations/times associated with the event"
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


class CategoryResult(BaseModel):
    """A single EONET category object."""

    id: str = Field(..., description="The unique ID of the category")
    title: str = Field(..., description="The EONET-provided title of the category")
    layers: str = Field(..., description="EONET endpoint URL for the category's layers")


class GetEventsInput(BaseModel):
    """Input model for get_events."""

    model_config = ConfigDict(extra="forbid")

    endpoint: Annotated[
        str,
        Field(
            ...,
            min_length=7,
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

    title: str | None = Field(None, description="The EONET-provided title of the response")
    link: str | None = Field(None, description="The API endpoint URL that was used to get the response")
    description: str | None = Field(
        None, description="Information describing what was requested, if available"
    )
    type: str | None = Field(None, description="The type of result if GeoJSON is requested")
    events: list[EventResult] | None = Field(
        None, description="The list of results if an event or a category was requested"
    )
    features: list[GeoJSONResult] | None = Field(
        None, description="The list of results if GeoJSON was requested"
    )
    categories: list[CategoryResult] | None = Field(
        None, description="The list of results if layers were requested"
    )

