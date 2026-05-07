"""Direct CMR tool search tool."""

import logging

from langfuse import observe

from models.pagination import (
    MANDATORY_FIELDS_DEFAULT,
    CursorParam,
    LimitParam,
)
from models.tools.cmr_search import SearchStatus
from models.tools.get_tools import (
    GetToolsInput,
    GetToolsOutput,
)
from util.cmr.client import CMRError, search_cmr
from util.cmr.search_tools import fetch_association_ids, normalize_tool_item
from util.langfuse import trace_update
from util.pagination import apply_field_filter, encode_cursor, resolve_cursor

logger = logging.getLogger(__name__)


@observe(name="get_tools")
def get_tools(  # pylint: disable=too-many-return-statements
    collection_concept_id: str | None = None,
    keyword: str | None = None,
    limit: LimitParam = 10,
    cursor: CursorParam = None,
    fields: list[str] | None = None,
) -> dict:
    """Search CMR tools by parent collection, keyword, or type.

    When collection_concept_id is provided, performs a two-phase lookup: fetches the
    collection's tool association IDs, then retrieves the full UMM-T records for those IDs.
    When keyword or type is provided without collection_concept_id, queries CMR tools directly.

    Pagination: use limit (default 10, max 50) and cursor to page through results.
    Pass the next_cursor from a previous response as cursor to advance to the next page.
    Cursors are query-scoped: they lock in the original search parameters and cannot be reused
    across different tools or different queries. To change search parameters, start a new search
    without a cursor.
    """
    trace_update(
        tags=["cmr", "tools"],
        metadata={
            "collection_concept_id": collection_concept_id,
            "keyword": keyword,
        },
    )

    try:
        params = GetToolsInput(
            collection_concept_id=collection_concept_id,
            keyword=keyword,
            limit=limit,
            cursor=cursor,
            fields=fields or [],
        )
    except (ValueError, TypeError) as exc:
        logger.warning("get_tools input validation failed: %s", exc)
        return GetToolsOutput(
            status=SearchStatus.ERROR,
            next_cursor=None,
            error_message=str(exc),
        ).model_dump()

    current_inputs = {
        "collection_concept_id": params.collection_concept_id,
        "keyword": params.keyword,
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
                return GetToolsOutput(
                    status=SearchStatus.ERROR,
                    error_message="Cursor parameters are query-scoped. You cannot change search parameters when paginating.",
                    next_cursor=None,
                ).model_dump()
        except ValueError as exc:
            return GetToolsOutput(
                status=SearchStatus.ERROR,
                next_cursor=None,
                error_message=str(exc),
            ).model_dump()

    tool_ids: list[str] = []

    if search_params is None:
        # Phase 1: fetch the collection record to discover its direct tool associations.
        if params.collection_concept_id:
            try:
                found_ids = fetch_association_ids(params.collection_concept_id, "tools")
            except (CMRError, ValueError, TypeError) as exc:
                logger.warning(
                    "Collection lookup failed for %s: %s", params.collection_concept_id, exc
                )
                return GetToolsOutput(
                    status=SearchStatus.ERROR,
                    next_cursor=None,
                    error_message=str(exc),
                ).model_dump()
            except Exception:  # pylint: disable=broad-exception-caught
                logger.exception(
                    "Unexpected error during collection lookup for %s",
                    params.collection_concept_id,
                )
                return GetToolsOutput(
                    status=SearchStatus.ERROR,
                    next_cursor=None,
                    error_message="An unexpected internal error occurred during collection lookup.",
                ).model_dump()

            if found_ids is None:
                return GetToolsOutput(status=SearchStatus.NO_RESULTS, next_cursor=None).model_dump()
            tool_ids = found_ids
            if not tool_ids and not params.keyword:
                return GetToolsOutput(status=SearchStatus.NO_RESULTS, next_cursor=None).model_dump()

        # Phase 2 params: build from Phase 1 results or direct keyword search.
        search_params = {}
        if tool_ids:
            search_params["concept_id[]"] = tool_ids
        if params.keyword:
            search_params["keyword"] = params.keyword

    try:
        tool_page = next(
            search_cmr(
                concept_type="tool",
                search_params=search_params,
                page_size=params.limit,
                search_after=search_after,
            ),
            None,
        )
    except (CMRError, ValueError, TypeError) as exc:
        logger.warning("Tool fetch failed for collection %s: %s", params.collection_concept_id, exc)
        return GetToolsOutput(
            status=SearchStatus.ERROR,
            next_cursor=None,
            error_message=str(exc),
        ).model_dump()
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception("Unexpected error during tool fetch for %s", params.collection_concept_id)
        return GetToolsOutput(
            status=SearchStatus.ERROR,
            next_cursor=None,
            error_message="An unexpected internal error occurred during tool fetch.",
        ).model_dump()

    if tool_page is None:
        return GetToolsOutput(status=SearchStatus.NO_RESULTS, next_cursor=None).model_dump()

    tools = [normalize_tool_item(item) for item in tool_page.items]
    status = SearchStatus.SUCCESS if tools else SearchStatus.NO_RESULTS
    cursor_payload = {
        "token": tool_page.search_after,
        "params": search_params,
        "inputs": current_inputs,
    }
    next_cursor = (
        encode_cursor("cmr", cursor_payload)
        if tool_page.search_after and len(tool_page.items) == params.limit
        else None
    )
    response_dict = GetToolsOutput(
        status=status,
        tools=tools,
        total_hits=tool_page.total_hits,
        next_cursor=next_cursor,
    ).model_dump()

    if params.fields:
        apply_field_filter(response_dict["tools"], params.fields, MANDATORY_FIELDS_DEFAULT)

    return response_dict
