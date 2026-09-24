"""Harmony get transformationjob status tool."""

import logging

from langfuse import observe
from fastmcp.server.dependencies import get_access_token

from models.pagination import CursorParam, LimitParam
from models.tools.get_transformation_job_status import (
    GetTransformationJobStatusInput,
    GetTransformationJobStatusOutput,
)
from util.harmony.client import get_client
from util.langfuse import trace_update
from util.pagination import apply_field_filter, encode_cursor, resolve_cursor

logger = logging.getLogger(__name__)

_TERMINAL_STATUSES = {"successful", "complete_with_errors"}
_CURSOR_NAMESPACE = "harmony_job_status"
_MANDATORY_FIELDS = frozenset({"job_id", "status", "message", "progress", "total_hits", "next_cursor"})


@observe(name="get_transformation_job_status")
def get_transformation_job_status(
    job_id: str,
    limit: LimitParam = 10,
    cursor: CursorParam = None,
    fields: list[str] | None = None,
) -> dict:
    """Get the current status, progress percentage, and metadata for a Harmony job.

    Pagination: Once a job reaches a terminal status, Harmony's full list of result/download
    links is fetched and sliced in-memory; total_hits reflects the full link count for that
    call. Pass the returned next_cursor into cursor to advance to the next page.
    Cursors are job-scoped: they lock in the original job_id and cannot be reused for a
    different job. To check a different job, start a new call without a cursor.

    fields: job_id, status, message, progress, total_hits, and next_cursor are always
    returned regardless of what is specified here.

    Note: if this call fails (e.g., input validation, cursor error, or a Harmony API
    error), code will contain the specific error type (e.g., "ValueError") and
    description will contain the error details, instead of a real Harmony job status.
    """

    trace_update(
        tags=["harmony", "job_status"],
        metadata={"job_id": job_id},
    )

    # Validate Input
    try:
        params = GetTransformationJobStatusInput(
            job_id=job_id, limit=limit, cursor=cursor, fields=fields or []
        )
    except (ValueError, TypeError) as exc:
        logger.warning("get_transformation_job_status input validation failed: %s", exc)
        return GetTransformationJobStatusOutput(
            code=type(exc).__name__,
            description=str(exc),
        ).model_dump()

    offset = 0
    job_id = params.job_id
    if params.cursor:
        try:
            cursor_value = resolve_cursor(params.cursor, _CURSOR_NAMESPACE)
            offset = cursor_value.get("offset", 0)
            cursor_job_id = cursor_value.get("job_id")

            if cursor_job_id and cursor_job_id != params.job_id:
                return GetTransformationJobStatusOutput(
                    code="CursorScopeError",
                    description="Cursor parameters are job-scoped. You cannot change job_id when paginating.",
                ).model_dump()

            job_id = cursor_job_id or params.job_id

        except ValueError as exc:
            return GetTransformationJobStatusOutput(
                code=type(exc).__name__,
                description=str(exc),
            ).model_dump()

    # Execute Harmony Status Request
    all_links: list[str] = []
    try:
        token = get_access_token().token
        client = get_client(token)
        status = client.status(job_id)
        if status.get("status") in _TERMINAL_STATUSES:
            all_links = list(client.result_urls(job_id))
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.error("Error communicating with Harmony API: %s", exc, exc_info=True)
        return GetTransformationJobStatusOutput(
            code=type(exc).__name__,
            description=f"Failed to fetch job status from Harmony: {str(exc)}",
        ).model_dump()

    total_hits = len(all_links)
    page_links = all_links[offset : offset + params.limit]
    next_cursor = (
        encode_cursor(_CURSOR_NAMESPACE, {"offset": offset + params.limit, "job_id": job_id})
        if offset + params.limit < total_hits
        else None
    )

    # Parse/validate the Harmony response into our output model
    try:
        parsed = GetTransformationJobStatusOutput(**status)
        parsed.job_id = job_id
        parsed.links = page_links
        parsed.total_hits = total_hits
        parsed.next_cursor = next_cursor
    except (ValueError, TypeError) as exc:
        logger.error(
            "Harmony job status response did not match expected schema: %s",
            exc,
            exc_info=True,
        )
        return GetTransformationJobStatusOutput(
            code=type(exc).__name__,
            description=f"Unexpected response shape from Harmony: {exc}",
        ).model_dump()

    response_dict = parsed.model_dump(mode="json", by_alias=True)

    if params.fields:
        apply_field_filter([response_dict], params.fields, _MANDATORY_FIELDS)

    return response_dict
