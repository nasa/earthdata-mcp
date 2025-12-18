"""
Output model for temporal range queries.

Defines the structure of temporal range query results.
"""

from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional


class TemporalRangeOutput(BaseModel):
    """
    Output model for temporal range queries.

    Contains the extracted start and end dates from natural language queries.
    Both dates are optional to support open-ended ranges (e.g., "after 2024" or "before June").
    """

    StartDate: Optional[datetime] = Field(
        None,
        alias="start_date",
        description="Start date as datetime object with timezone",
        examples=["2024-06-01T00:00:00+00:00"],
    )
    EndDate: Optional[datetime] = Field(
        None,
        alias="end_date",
        description="End date as datetime object with timezone",
        examples=["2024-08-31T23:59:59+00:00"],
    )
    reasoning: Optional[str] = Field(
        None,
        description="Explanation of how the temporal range was interpreted",
    )

    class Config:
        """Pydantic configuration."""

        populate_by_name = True
        json_schema_extra = {
            "examples": [
                {
                    "StartDate": "2024-06-01T00:00:00+00:00",
                    "EndDate": "2024-08-31T23:59:59+00:00",
                    "reasoning": "Query refers to summer 2024, interpreted as June 1st to August 31st",
                },
                {
                    "StartDate": "2024-01-01T00:00:00+00:00",
                    "EndDate": None,
                    "reasoning": "Query refers to 'after 2024', open-ended range starting from January 1st 2024",
                },
                {
                    "StartDate": None,
                    "EndDate": None,
                    "reasoning": "No specific temporal range mentioned in query",
                },
            ]
        }
