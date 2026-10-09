"""Input model for the control_transformation_job MCP tool."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ControlTransformationJobInput(BaseModel):
    """Input model for the control_transformation_job MCP tool."""

    model_config = ConfigDict(extra="forbid")

    job_id: str = Field(..., description="The ID of the Harmony job to control.")
    action: Literal["cancel", "pause", "resume"] = Field(
        ..., description="The control action to perform on the job."
    )
