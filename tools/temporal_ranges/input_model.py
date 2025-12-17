"""
Input model for temporal range queries.

Validates natural language strings describing desired time periods.
"""

from pydantic import BaseModel


class TemporalRangeInput(BaseModel):
    """
    Input model for temporal range queries.

    Validates natural language strings describing desired time periods.
    """

    timerange_string: str
