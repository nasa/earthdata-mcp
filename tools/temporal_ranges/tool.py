"""
Temporal Ranges Tool

Update this once the tool is implemented
"""

from datetime import datetime
from typing import Any
from pydantic import BaseModel


class DateRange(BaseModel):
    """
    Update this once the tool is implemented
    """

    start: datetime | None = None
    end: datetime | None = None


def get_temporal_ranges(daterange: DateRange) -> Any:
    """Get a list of collections form CMR based on keywords.

    Args:
        keywords: A string of text to search collections with.
    """
    return [{"StartDate": daterange.start, "EndDate": daterange.end}]
