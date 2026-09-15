"""Shared models for harmony tools."""

from pydantic import BaseModel, Field

class BaseHarmonyToolOutput(BaseModel):
    """Base output model shared by all harmony tools."""

    # ---------------------------------------------------------
    # Error Handling Fields
    # ---------------------------------------------------------
    code: str | None = Field(default=None, description="Error code if the request failed.")
    description: str | None = Field(default=None, description="Error description if the request failed.")