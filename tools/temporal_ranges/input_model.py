"""
Input model for temporal range queries.

Validates natural language strings describing desired time periods.
"""

from pydantic import BaseModel, Field


class TimeRangeInput(BaseModel):
    """
    Input model for time range queries.

    Validates natural language strings describing desired time periods.
    """

    # Renamed from 'timerange_string' to 'query' to encourage passing full user context
    # rather than pre-extracted time phrases. This gives the internal LLM more context
    # for accurate temporal extraction.
    query: str = Field(
        ...,
        description="The full user query containing temporal references (e.g., 'Find aerosol data for the last 5 years' or 'Show me data during California fire season'). The tool will extract the relevant time range from the complete context."
    )
