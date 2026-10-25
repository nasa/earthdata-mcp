"""Input model for the submit_transformation_job MCP tool."""

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Shapefile extensions accepted by the Harmony API.
_ALLOWED_SHAPE_EXTENSIONS = frozenset({".zip", ".shz", ".json", ".geojson", ".kml"})


class SubmitTransformationJobInput(BaseModel):
    """Input model for the submit_transformation_job MCP tool."""

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

    @field_validator("shape")
    @classmethod
    def validate_shape_path(cls, v: str | None) -> str | None:
        """Reject path traversal sequences and disallowed file extensions.

        Without this check an authenticated caller (or an LLM agent that has
        been manipulated via indirect prompt injection) could supply an
        arbitrary server-side path such as
        ``/var/run/secrets/kubernetes.io/serviceaccount/token``, causing
        harmony-py to open and upload that file to the Harmony API.
        """
        if v is None:
            return v
        p = Path(v)
        # Reject traversal components regardless of OS.
        if any(part in ("..", ".") for part in p.parts if part not in (".", "/")):
            raise ValueError("shape path must not contain directory traversal components")
        if ".." in v:
            raise ValueError("shape path must not contain '..'")
        if p.suffix.lower() not in _ALLOWED_SHAPE_EXTENSIONS:
            raise ValueError(
                f"shape must be one of the supported file types: "
                f"{', '.join(sorted(_ALLOWED_SHAPE_EXTENSIONS))}"
            )
        return v
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
