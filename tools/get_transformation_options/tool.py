"""Harmony get transformation options tool."""

import logging

import harmony
from fastmcp.exceptions import ToolError
from fastmcp.server.dependencies import get_access_token
from langfuse import observe

from models.tools.get_transformation_options import GetTransformationOptionsInput
from util.harmony.client import get_client
from util.langfuse import trace_update

logger = logging.getLogger(__name__)


@observe(name="get_transformation_options")
def get_transformation_options(
    collection_concept_id: str | None = None,
    short_name: str | None = None,
) -> dict:
    """Look up what Harmony operations a collection supports.

    Provide either collection_concept_id (CMR concept id) or short_name. Returns
    which subsetting/reprojection/reformatting features are available, the
    services that implement them, supported output formats, and variables.
    """
    trace_update(
        tags=["harmony"],
        metadata={
            "collection_concept_id": collection_concept_id,
            "short_name": short_name
        },
    )

    # Validate Input
    try:
        GetTransformationOptionsInput(
            collection_id=collection_concept_id,
            short_name=short_name,
        )
    except (ValueError, TypeError) as exc:
        logger.warning("get_transformation_options input validation failed: %s", exc)
        raise ToolError(f"get_transformation_options {type(exc).__name__}: {str(exc)}") from exc

    kwargs = {}
    if collection_concept_id:
        kwargs["collection_id"] = collection_concept_id
    if short_name:
        kwargs["short_name"] = short_name
    # Set to version 3
    kwargs["capabilities_version"] = "3"

    # Execute Harmony Capabilities Request
    try:
        token = get_access_token().token
        client = get_client(token)
        request = harmony.CapabilitiesRequest(**kwargs)
        result = client.submit(request)
    except Exception as exc:
        logger.error("Error communicating with Harmony API: %s", exc, exc_info=True)
        raise ToolError(f"get_transformation_options {type(exc).__name__}: {str(exc)}") from exc

    return result
