"""Input and output models for the get_events MCP tool."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from models.pagination import LimitParam
from models.tools.cmr_search import BaseCmrSearchOutput


class EventResult(BaseModel):
    """A single EONET object (could be an event, category, source, or layer)."""

    id: str = Field(..., description="The unique ID of the EONET result")
    title: str = Field(..., description="The EONET-provided title of the result")
    metadata: dict[str, str] = Field(..., description="The EONET result metadata")
    description: str | None = Field(
        None, description="The primary description of the EONET object, if available"
    )


class GetEventsInput(BaseModel):
    """Input model for get_events."""

    model_config = ConfigDict(extra="forbid")

    endpoint: Annotated[
        str,
        Field(
            ...,
            min_length=1,
            pattern=r"v\d+/[a-z]+/?[a-z]*",
            description="The EONET endpoint for the API call (e.g. '/v3/events').",
        ),
    ]
    event_params: Annotated[
        dict | None,
        Field(
            None,
            description=(
                "Optional. A dictionary of filters to apply to the EONET API call. "
                "Detailed descriptions of each filter parameter can be found at "
                "https://eonet.gsfc.nasa.gov/docs/v3"
            ),
        ),
    ]
    limit: LimitParam = 10


class GetEventsOutput(BaseCmrSearchOutput):
    """Output model for get_events."""

    events: list[EventResult] = Field(
        default_factory=list, description="List of matched EONET events"
    )
