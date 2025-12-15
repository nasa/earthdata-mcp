from pydantic import BaseModel, Field


class TemporalRangeInput(BaseModel):
    """
    Input model for temporal range queries.

    Validates natural language strings describing desired time periods.
    """

    timerange_string: str
