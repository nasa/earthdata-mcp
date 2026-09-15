from pydantic import BaseModel, ConfigDict, Field
from models.tools.harmony import BaseHarmonyToolOutput

class GetJobStatusInput(BaseModel):
    """Input model for the get_job_status MCP tool."""

    model_config = ConfigDict(extra="forbid")
    
    job_id: str = Field(..., description="The ID of the Harmony job to check.")


class GetJobStatusOutput(BaseHarmonyToolOutput):
    """Output model for the get_job_status MCP tool."""

    # ---------------------------------------------------------
    # Harmony API Status Response Fields
    # ---------------------------------------------------------
    status: str | None = Field(
        default=None, 
        description="Current status of the job (e.g., 'running', 'successful', 'failed', 'canceled')."
    )
    message: str | None = Field(
        default=None, 
        description="Human-readable message regarding the job status."
    )
    progress: int | float | None = Field(
        default=None, 
        description="Progress percentage of the job (0-100)."
    )
    created_at: str | None = Field(
        default=None, 
        description="UTC timestamp (ISO 8601) when the job was created."
    )
    updated_at: str | None = Field(
        default=None, 
        description="UTC timestamp (ISO 8601) when the job was last updated."
    )
    created_at_local: str | None = Field(
        default=None, 
        description="Local timestamp (ISO 8601) when the job was created."
    )
    updated_at_local: str | None = Field(
        default=None, 
        description="Local timestamp (ISO 8601) when the job was last updated."
    )
    request: str | None = Field(
        default=None, 
        description="The original Harmony request URL with parameters."
    )
    num_input_granules: int | None = Field(
        default=None, 
        description="Total number of input granules processed by the job."
    )
    data_expiration: str | None = Field(
        default=None, 
        description="UTC timestamp (ISO 8601) when the job's data will expire."
    )
    data_expiration_local: str | None = Field(
        default=None, 
        description="Local timestamp (ISO 8601) when the job's data will expire."
    )
