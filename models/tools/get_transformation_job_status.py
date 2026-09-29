"""Input and output models for the get_transformation_job_status MCP tool."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from models.tools.harmony import BaseHarmonyToolOutput
from models.pagination import CursorParam, FieldsParam, LimitParam

class GetTransformationJobStatusInput(BaseModel):
    """Input model for the get_transformation_job_status MCP tool."""

    model_config = ConfigDict(extra="forbid")

    job_id: str = Field(..., description="The ID of the Harmony job to check.")
    limit: LimitParam = 10
    cursor: CursorParam = None
    fields: FieldsParam


class GetTransformationJobStatusOutput(BaseHarmonyToolOutput):
    """Output model for the get_transformation_job_status MCP tool."""

    job_id: str | None = Field(
        default=None,
        description="Unique identifier (UUID) for the job"
    )
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
    created_at: datetime | None = Field(
        default=None, 
        description="UTC timestamp (ISO 8601) when the job was created."
    )
    updated_at: datetime | None = Field(
        default=None, 
        description="UTC timestamp (ISO 8601) when the job was last updated."
    )
    created_at_local: datetime | None = Field(
        default=None, 
        description="Local timestamp (ISO 8601) when the job was created."
    )
    updated_at_local: datetime | None = Field(
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
    data_expiration: datetime | None = Field(
        default=None, 
        description="UTC timestamp (ISO 8601) when the job's data will expire."
    )
    data_expiration_local: datetime | None = Field(
        default=None, 
        description="Local timestamp (ISO 8601) when the job's data will expire."
    )
    links: list[str] = Field(
        default_factory=list,
        description="Links to job result files",
    )
    total_hits: int = Field(default=0, description="Total number of matching items")
    next_cursor: str | None = Field(
        default=None,
        description="Pagination token for the next page; None when no more results"
    )
