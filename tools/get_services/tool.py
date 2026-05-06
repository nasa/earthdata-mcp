"""Direct CMR service search tool."""

import logging

from langfuse import observe

from models.pagination import CursorParam, LimitParam, decode_cursor, encode_cursor
from models.tools.cmr_search import SearchStatus
from models.tools.get_services import (
    CollectionConceptIdParam,
    GetServicesInput,
    GetServicesOutput,
)
from util.cmr.client import CMRError, search_cmr
from util.cmr.search_tools import normalize_service_item
from util.langfuse import trace_update

logger = logging.getLogger(__name__)


@observe(name="get_services")
def get_services(  # pylint: disable=too-many-return-statements
    collection_concept_id: CollectionConceptIdParam,
    keyword: str | None = None,
    type: str | None = None,
    limit: LimitParam = 10,
    cursor: CursorParam = None,
) -> dict:
    """Search CMR services for a single parent collection, returning all associated normalized results.

    The returned items use snake_cased keys that map directly to the UMM-S schema, including:
    - concept_id: CMR service concept ID
    - native_id: The native ID of the service record
    - revision_id: The revision ID of the service metadata
    - provider_id: The provider ID of the service
    - name: The name of the service
    - long_name: The long name of the service
    - type: The type of the service
    - version: The edition or version of the service
    - description: A brief description of the service
    - url: Primary endpoint URL information
    - related_urls: Documentation, guides, or other related links
    - access_constraints: Authentication or authorization requirements
    - use_constraints: Legal restrictions or usage limits
    - service_options: Subset types, supported projections, output formats
    - operation_metadata: Operation names and distributed computing platform
    """
    trace_update(
        tags=["cmr", "services"],
        metadata={
            "collection_concept_id": collection_concept_id,
            "keyword": keyword,
            "type": type,
        },
    )

    try:
        params = GetServicesInput(
            collection_concept_id=collection_concept_id,
            keyword=keyword,
            type=type,
            limit=limit,
            cursor=cursor,
        )
    except (ValueError, TypeError) as exc:
        logger.warning("get_services input validation failed: %s", exc)
        return GetServicesOutput(
            status=SearchStatus.ERROR,
            next_cursor=None,
            error_message=str(exc),
        ).model_dump()

    # Decode cursor before Phase 1.
    search_after = None
    if params.cursor:
        try:
            parsed = decode_cursor(params.cursor)
            if parsed.get("backend") != "cmr":
                raise ValueError(
                    "Cursor is not valid for this tool. Cursors cannot be reused across "
                    "different tools. Start a new search without a cursor parameter."
                )
            search_after = parsed.get("value")
        except ValueError as exc:
            return GetServicesOutput(
                status=SearchStatus.ERROR, next_cursor=None, error_message=str(exc)
            ).model_dump()

    service_ids: list[str] = []

    # Phase 1: Find linked services. CMR collections only list the IDs of their associated
    # services, not the full details. We first fetch the collection to get this list of IDs.
    try:
        collection_page = next(
            search_cmr(
                concept_type="collection",
                search_params={"concept_id": params.collection_concept_id},
                page_size=1,
            ),
            None,
        )
    except (CMRError, ValueError, TypeError) as exc:
        logger.warning("Collection lookup failed for %s: %s", params.collection_concept_id, exc)
        return GetServicesOutput(
            status=SearchStatus.ERROR,
            next_cursor=None,
            error_message=str(exc),
        ).model_dump()
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception(
            "Unexpected error during collection lookup for %s",
            params.collection_concept_id,
        )
        return GetServicesOutput(
            status=SearchStatus.ERROR,
            next_cursor=None,
            error_message="An unexpected internal error occurred during collection lookup.",
        ).model_dump()

    if not collection_page or not collection_page.items:
        return GetServicesOutput(status=SearchStatus.NO_RESULTS, next_cursor=None).model_dump()

    service_ids = (
        collection_page.items[0].get("meta", {}).get("associations", {}).get("services", [])
    )
    if not service_ids:
        return GetServicesOutput(status=SearchStatus.NO_RESULTS, next_cursor=None).model_dump()

    # Phase 2: Fetch the actual service details using the IDs we found.
    search_params = {"concept_id[]": service_ids}
    if params.keyword:
        search_params["keyword"] = params.keyword
    if params.type:
        search_params["type"] = params.type

    try:
        service_page = next(
            search_cmr(
                concept_type="service",
                search_params=search_params,
                page_size=params.limit,
                search_after=search_after,
            ),
            None,
        )
    except (CMRError, ValueError, TypeError) as exc:
        logger.warning(
            "Service fetch failed for collection %s: %s", params.collection_concept_id, exc
        )
        return GetServicesOutput(
            status=SearchStatus.ERROR,
            next_cursor=None,
            error_message=str(exc),
        ).model_dump()
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception(
            "Unexpected error during service fetch for %s", params.collection_concept_id
        )
        return GetServicesOutput(
            status=SearchStatus.ERROR,
            next_cursor=None,
            error_message="An unexpected internal error occurred during service fetch.",
        ).model_dump()

    if service_page is None or not service_page.items:
        return GetServicesOutput(status=SearchStatus.NO_RESULTS, next_cursor=None).model_dump()

    services = [normalize_service_item(item) for item in service_page.items]
    next_cursor = (
        encode_cursor("cmr", service_page.search_after)
        if service_page.search_after and len(service_page.items) == params.limit
        else None
    )

    return GetServicesOutput(
        status=SearchStatus.SUCCESS,
        services=services,
        total_hits=service_page.total_hits,
        next_cursor=next_cursor,
    ).model_dump()
