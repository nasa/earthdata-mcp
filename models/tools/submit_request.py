from pydantic import BaseModel, ConfigDict, Field
from models.tools.get_job_status import GetJobStatusOutput


class SubmitRequestInput(BaseModel):
    """Input model for the submit_request MCP tool."""
    
    # Forbid extra fields to prevent users/LLMs from hallucinating unsupported arguments
    model_config = ConfigDict(extra="forbid")

    collection_id: str = Field(
        ..., 
        description="CMR concept ID of the collection (e.g., C1234567-PROV)."
    )
    bbox: list[float] | None = Field(
        default=None, 
        description="Bounding box array in degrees: [west, south, east, north]."
    )
    shape: str | None = Field(
        default=None, 
        description="Local path to a supported Harmony shapefile-subsetting file (.zip/.shz/.json/.geojson/.kml)."
    )
    temporal_start: str | None = Field(
        default=None, 
        description="ISO 8601 start timestamp for temporal subsetting."
    )
    temporal_stop: str | None = Field(
        default=None, 
        description="ISO 8601 stop timestamp for temporal subsetting."
    )
    variables: list[str] | None = Field(
        default=None, 
        description="List of specific variable names to subset."
    )
    format: str | None = Field(
        default=None, 
        description="Desired output format (e.g., 'image/tiff', 'application/x-netcdf4')."
    )
    crs: str | None = Field(
        default=None, 
        description="Target Coordinate Reference System for reprojection (e.g., 'EPSG:4326')."
    )
    width: int | None = Field(
        default=None, 
        description="Target width in pixels for spatial reprojection/resampling."
    )
    height: int | None = Field(
        default=None, 
        description="Target height in pixels for spatial reprojection/resampling."
    )
    max_results: int | None = Field(
        default=None, 
        description="Maximum number of granules/results to process."
    )
    granule_ids: list[str] | None = Field(
        default=None, 
        description="Optional list of specific CMR granule concept IDs to process."
    )


class SubmitRequestOutput(GetJobStatusOutput):
    """Output model for the submit_request MCP tool.
    
    Inherits all status and error fields from GetJobStatusOutput.
    """

    job_id: str | None = Field(
        default=None, 
        description="The unique identifier for the submitted Harmony job."
    )