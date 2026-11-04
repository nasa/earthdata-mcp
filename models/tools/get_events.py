"""Input and output models for the get_events MCP tool."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from models.tools.cmr_search import BaseToolOutput


class CATEGORIES:
    """Available EONET API categories."""
    DROUGHT = "drought"
    DUST_HAZE = "dustHaze"
    EARTHQUAKES = "earthquakes"
    FLOODS = "floods"
    LANDSLIDES = "landslides"
    MANMADE = "manmade"
    SEA_LAKE_ICE = "seaLakeIce"
    SEVERE_STORMS = "severeStorms"
    SNOW = "snow"
    TEMPERATURE_EXTREMES = "tempExtremes"
    VOLCANOES = "volcanoes"
    WATER_COLOR = "waterColor"
    WILDFIRES = "wildfires"


class ENDPOINTS:
    """Available EONET API endpoints."""
    EVENTS = "events"
    GEOJSON = "events/geojson"


class GetEventsInput(BaseModel):
    """Input model for get_events."""

    model_config = ConfigDict(extra="forbid")

    source: Annotated[
        str,
        Field(
            "",
            description="The source of the events data.",
        ),
    ]
    category: Annotated[
        CATEGORIES | None,
        Field(
            None,
            description="The category to filter events by.",
        ),
    ]
    status: Annotated[
        str | None,
        Field(
            None,
            description="The status to filter events by (open, closed, all).",
        ),
    ]
    limit: Annotated[
        int,
        Field(
            5,
            description="The maximum number of events to retrieve.",
        ),
    ]
    days: Annotated[
        int | None,
        Field(
            None,
            description="Including the present day, how far to look back for events (measured in days).",
        ),
    ]
    start: Annotated[
        str | None,
        Field(
            None,
            pattern=r"^\d{4}-\d{2}-\d{2}$",
            description="The start date to filter events by (YYYY-MM-DD).",
        ),
    ]
    end: Annotated[
        str | None,
        Field(
            None,
            pattern=r"^\d{4}-\d{2}-\d{2}$",
            description="The end date to filter events by (YYYY-MM-DD).",
        ),
    ]
    magID: Annotated[
        str | None,
        Field(
            None,
            description="The magnitude ID to filter events by (measures the strength of an event in units specific to the event).",
        ),
    ]
    magMin: Annotated[
        float | None,
        Field(
            None,
            description="The minimum magnitude to filter events by.",
        ),
    ]
    magMax: Annotated[
        float | None,
        Field(
            None,
            description="The maximum magnitude to filter events by.",
        ),
    ]
    bbox: Annotated[
        str,
        Field(
            "-180.0,-90.0,180.0,90.0",
            description="The bounding box to filter events by, using the following syntax: minLong,maxLat,maxLong,minLat.",
        ),
    ]


class GetEventsOutput(BaseToolOutput):
    """Output model for get_events."""

    title: str = Field("", description="The title of the response, if available")
    description: str = Field("", description="Information describing what was requested, if available")
    link: str = Field("", description="The API endpoint URL that was used to get the response")
    data: dict = Field({}, description="Results from the EONET API call")

