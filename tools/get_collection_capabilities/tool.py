import logging
import datetime

from langfuse import observe
from models.tools.get_collection_capabilities import GetCollectionCapabilitiesInput, GetCollectionCapabilitiesOutput
from util.harmony.client import get_client
from util.langfuse import trace_update

import harmony

logger = logging.getLogger(__name__)


@observe(name="get_collection_capabilities")
def get_collection_capabilities(
    session_id: str,
    collection_concept_id: str | None = None,
    short_name: str | None = None,
    access_token: str | None = None,
) -> dict:
    """Look up what Harmony operations a collection supports.

    Provide either collection_id (CMR concept id) or short_name. Returns
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

    # 1. Validate Input
    try:
        params = GetCollectionCapabilitiesInput(
            collection_id=collection_concept_id,
            short_name=short_name,
        )
    except (ValueError, TypeError) as exc:
        logger.error("get_collection_capabilities input validation failed: %s", exc)
        return GetCollectionCapabilitiesOutput(
            code=type(exc).__name__,
            description=str(exc)
        ).model_dump()

    kwargs = {}
    if collection_concept_id:
        kwargs["collection_id"] = collection_concept_id
    if short_name:
        kwargs["short_name"] = short_name

    # 2. Execute Harmony Request
    try:
        client = get_client(access_token)
        request = harmony.CapabilitiesRequest(**kwargs)
        result = client.submit(request)
    except Exception as exc:
        logger.error("Error communicating with Harmony API: %s", exc, exc_info=True)
        return GetCollectionCapabilitiesOutput(
            code=type(exc).__name__,
            description=f"Failed to fetch capabilities from Harmony: {str(exc)}"
        ).model_dump()

    return result
