import logging

from langfuse import observe
from models.tools.get_job_status import GetJobStatusInput, GetJobStatusOutput
from util.harmony.client import get_client, _json_safe
from util.langfuse import trace_update
from fastmcp.server.dependencies import get_access_token

logger = logging.getLogger(__name__)


@observe(name="get_job_status")
def get_job_status(job_id: str) -> dict:
    """Get the current status, progress percentage, and metadata for a Harmony job."""
    
    trace_update(
        tags=["harmony", "job_status"],
        metadata={
            "job_id": job_id
        },
    )

    # Validate Input
    try:
        params = GetJobStatusInput(
            job_id=job_id
        )
    except (ValueError, TypeError) as exc:
        logger.error("get_job_status input validation failed: %s", exc)
        return GetJobStatusOutput(
            code=type(exc).__name__,
            description=str(exc)
        ).model_dump()

    # Execute Harmony Status Request
    try:
        token = get_access_token().token
        client = get_client(token)
        status = client.status(job_id)
        
    except Exception as exc:
        logger.error("Error communicating with Harmony API: %s", exc, exc_info=True)
        return GetJobStatusOutput(
            code=type(exc).__name__,
            description=f"Failed to fetch job status from Harmony: {str(exc)}"
        ).model_dump()

    return _json_safe(status)