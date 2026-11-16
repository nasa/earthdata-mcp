"""Input and output models for the get_events MCP tool."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from models.tools.cmr_search import BaseToolOutput

CATEGORIES_TYPE = Literal[
    "drought",
    "dustHaze",
    "earthquakes",
    "floods",
    "landslides",
    "manmade",
    "seaLakeIce",
    "severeStorms",
    "snow",
    "tempExtremes",
    "volcanoes",
    "waterColor",
    "wildfires",
]

STATUS_TYPE = Literal["open", "closed", "all"]

Source = Annotated[
    str | None,
    Field(
        None,
        description="The source of the events data.",
    ),
]

Category = Annotated[
    CATEGORIES_TYPE | None,
    Field(
        None,
        description="The category to filter events by.",
    ),
]

Status = Annotated[
    STATUS_TYPE,
    Field(
        "all",
        description=(
            "Filter by event status. Defaults to 'all' so both ongoing and ended events "
            "are returned. Set to 'open' when the user asks only for active/ongoing/current "
            "events; set to 'closed' for only ended events."
        ),
    ),
]

Limit = Annotated[
    int,
    Field(
        5,
        ge=1,
        le=50,
        description=(
            "Maximum number of events to retrieve (1-50). Default 5. EONET applies the "
            "limit after status filtering, so a stricter 'status' can reduce the final "
            "count below this value."
        ),
    ),
]

Days = Annotated[
    int | None,
    Field(
        None,
        description="Including the present day, how far to look back for events (measured in days).",
    ),
]

Start = Annotated[
    str | None,
    Field(
        None,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="The start date to filter events by (YYYY-MM-DD).",
    ),
]

End = Annotated[
    str | None,
    Field(
        None,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="The end date to filter events by (YYYY-MM-DD).",
    ),
]

MagId = Annotated[
    str | None,
    Field(
        None,
        description="The magnitude ID to filter events by (measures the strength of an event in units specific to the event).",
    ),
]

MagMin = Annotated[
    float | None,
    Field(
        None,
        description="The minimum magnitude to filter events by.",
    ),
]

MagMax = Annotated[
    float | None,
    Field(
        None,
        description="The maximum magnitude to filter events by.",
    ),
]

Bbox = Annotated[
    str | None,
    Field(
        None,
        description="The bounding box to filter events by, using the following syntax: minLong,maxLat,maxLong,minLat.",
    ),
]


class GetEventsInput(BaseModel):
    """Input model for get_events."""

    model_config = ConfigDict(extra="forbid")

    source: Source = None
    category: Category = None
    status: Status = "all"
    limit: Limit = 5
    days: Days = None
    start: Start = None
    end: End = None
    magID: MagId = None
    magMin: MagMin = None
    magMax: MagMax = None
    bbox: Bbox = None


class GetEventsOutput(BaseToolOutput):
    """Output model for get_events."""

    data: dict = Field({}, description="GeoJSON results from EONET")
