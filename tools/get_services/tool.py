"""Direct CMR service search tool."""

import logging

from langfuse import observe

from models.pagination import (
    MANDATORY_FIELDS_DEFAULT,
    CursorParam,
    LimitParam,
)
from models.tools.cmr_search import SearchStatus
from models.tools.get_services import (
    GetServicesInput,
    GetServicesOutput,
)
from util.cmr.client import CMRError, search_cmr
from util.cmr.search_tools import fetch_association_ids, normalize_service_item
from util.langfuse import trace_update
from util.pagination import apply_field_filter, encode_cursor, resolve_cursor

logger = logging.getLogger(__name__)


@observe(name="get_services")
def get_services(  # pylint: disable=too-many-return-statements,redefined-builtin
    collection_concept_id: str | None = None,
    keyword: str | None = None,
    type: str | None = None,
    limit: LimitParam = 10,
    cursor: CursorParam = None,
    fields: list[str] | None = None,
) -> dict:
    """Search CMR services by collection association, keyword, or type.

    Supports pagination via limit/cursor and field filtering via fields.
    Cursors are query-scoped: they lock in the original search parameters and cannot be reused
    across different tools or different queries. To change search parameters, start a new search
    without a cursor.

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
    - service_keywords: Controlled vocabulary for service capability
    - service_options: Subset types, supported projections, output formats
    - service_organizations: Organizations that run the service endpoint
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
            fields=fields or [],
        )
    except (ValueError, TypeError) as exc:
        logger.warning("get_services input validation failed: %s", exc)
        return GetServicesOutput(
            status=SearchStatus.ERROR,
            next_cursor=None,
            error_message=str(exc),
        ).model_dump()

    # Decode cursor before Phase 1.

    current_inputs = {
        "collection_concept_id": params.collection_concept_id,
        "keyword": params.keyword,
        "type": params.type,
    }
    search_after = None
    search_params = None  # sentinel: None means "must build via Phase 1"

    if params.cursor:
        try:
            cursor_value = resolve_cursor(params.cursor, "cmr")
            search_after = cursor_value.get("token")
            search_params = cursor_value.get("params", {})
            cursor_inputs = cursor_value.get("inputs", {})

            normalized_search = {k: v for k, v in current_inputs.items() if v}
            for k, v in normalized_search.items():
                if isinstance(v, list):
                    normalized_search[k] = sorted(v)

            normalized_cursor = {k: v for k, v in cursor_inputs.items() if v}
            for k, v in normalized_cursor.items():
                if isinstance(v, list):
                    normalized_cursor[k] = sorted(v)

            if normalized_search != normalized_cursor:
                return GetServicesOutput(
                    status=SearchStatus.ERROR,
                    error_message="Cursor parameters are query-scoped. You cannot change search parameters when paginating.",
                    next_cursor=None,
                ).model_dump()
        except ValueError as exc:
            return GetServicesOutput(
                status=SearchStatus.ERROR, next_cursor=None, error_message=str(exc)
            ).model_dump()

    service_ids: list[str] = []

    if search_params is None:
        # Phase 1: fetch the collection record to discover its direct service associations.
        if params.collection_concept_id:
            try:
                found_ids = fetch_association_ids(params.collection_concept_id, "services")
            except (CMRError, ValueError, TypeError) as exc:
                logger.warning(
                    "Collection lookup failed for %s: %s", params.collection_concept_id, exc
                )
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

            if found_ids is None:
                return GetServicesOutput(
                    status=SearchStatus.NO_RESULTS, next_cursor=None
                ).model_dump()
            service_ids = found_ids
            if not service_ids and not params.keyword and not params.type:
                return GetServicesOutput(
                    status=SearchStatus.NO_RESULTS, next_cursor=None
                ).model_dump()

        # Phase 2 params: build from Phase 1 results or direct keyword/type.
        search_params = {}
        if service_ids:
            search_params["concept_id[]"] = service_ids
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

    if service_page is None:
        return GetServicesOutput(status=SearchStatus.NO_RESULTS, next_cursor=None).model_dump()

    cursor_payload = {
        "token": service_page.search_after,
        "params": search_params,
        "inputs": current_inputs,
    }
    next_cursor = (
        encode_cursor("cmr", cursor_payload)
        if service_page.search_after and len(service_page.items) == params.limit
        else None
    )

    services = [normalize_service_item(item) for item in service_page.items]
    status = SearchStatus.SUCCESS if services else SearchStatus.NO_RESULTS
    response_dict = GetServicesOutput(
        status=status,
        services=services,
        total_hits=service_page.total_hits,
        next_cursor=next_cursor,
    ).model_dump()

    if params.fields:
        apply_field_filter(response_dict["services"], params.fields, MANDATORY_FIELDS_DEFAULT)

    return response_dict
