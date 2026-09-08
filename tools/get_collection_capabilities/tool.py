import logging
import datetime

from langfuse import observe
from models.tools.cmr_search import SearchStatus
from models.tools.get_citations import GetCitationsInput, GetCitationsOutput
from util.harmony.client import get_client
from util.cmr.search_tools import fetch_association_ids, normalize_citation_item
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

    logger.info("Token was passed in?:%s", access_token)

    if not collection_concept_id and not short_name:
        raise ValueError("Provide either collection_id or short_name")

    kwargs = {}
    if collection_concept_id:
        kwargs["collection_id"] = collection_concept_id
    if short_name:
        kwargs["short_name"] = short_name

    client = get_client(access_token)
    request = harmony.CapabilitiesRequest(**kwargs)
    result = client.submit(request)
    return _json_safe(result)

def _json_safe(value):
    """Recursively convert datetimes (harmony-py's status() returns some) to ISO strings."""
    if isinstance(value, datetime.datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value
