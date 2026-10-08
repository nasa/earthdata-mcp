"""Harmony control transformation job tool (cancel/pause/resume)."""

import logging
from typing import Literal

from langfuse import observe
from fastmcp.server.dependencies import get_access_token
from fastmcp.exceptions import ToolError
from models.tools.control_transformation_job import ControlTransformationJobInput
from models.tools.get_transformation_job_status import GetTransformationJobStatusOutput
from util.harmony.client import get_client
from util.langfuse import trace_update

logger = logging.getLogger(__name__)

_ACTIONS = {
    "cancel": lambda client, job_id: client.cancel(job_id),
    "pause": lambda client, job_id: client.pause(job_id),
    "resume": lambda client, job_id: client.resume(job_id),
}


@observe(name="control_transformation_job")
def control_transformation_job(
    job_id: str,
    action: Literal["cancel", "pause", "resume"],
) -> dict:
    """Cancel, pause, or resume a running or paused Harmony transformation job.

    action must be one of "cancel", "pause", or "resume". Use
    get_transformation_job_status first to check the job's current state if needed
    because resuming a job that isn't paused, or pausing one that's already
    terminal, will return an error from Harmony.

    Returns the job's status immediately after the action is applied.
    """
    trace_update(
        tags=["harmony", "control_job"],
        metadata={"job_id": job_id, "action": action},
    )

    # Validate Input
    try:
        ControlTransformationJobInput(job_id=job_id, action=action)
    except (ValueError, TypeError) as exc:
        logger.warning("control_transformation_job input validation failed: %s", exc)
        raise ToolError(f"control_transformation_job {type(exc).__name__}: {str(exc)}")

    # Execute Harmony Control Action
    try:
        token = get_access_token().token
        client = get_client(token)
        _ACTIONS[action](client, job_id)
        status = client.status(job_id)
    except Exception as exc:
        logger.error(
            "Error performing '%s' on Harmony job %s: %s", action, job_id, exc, exc_info=True
        )
        raise ToolError(f"control_transformation_job {type(exc).__name__}: {str(exc)}")

    # Parse/validate the Harmony status response
    try:
        parsed = GetTransformationJobStatusOutput(**status)
        parsed.job_id = job_id
    except (ValueError, TypeError) as exc:
        logger.error(
            "Harmony job status response did not match expected schema: %s",
            exc,
            exc_info=True,
        )
        raise ToolError(f"control_transformation_job {type(exc).__name__}: {str(exc)}")

    return parsed.model_dump(mode="json", by_alias=True)
