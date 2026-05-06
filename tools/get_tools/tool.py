"""Direct CMR tool search tool."""

import logging

from langfuse import observe

from models.pagination import (
    MANDATORY_FIELDS_DEFAULT,
    CursorParam,
    FieldsParam,
    LimitParam,
    apply_field_filter,
    decode_cursor,
    encode_cursor,
)
from models.tools.cmr_search import SearchStatus
from models.tools.get_tools import (
    GetToolsInput,
    GetToolsOutput,
)
from util.cmr.client import CMRError, search_cmr
from util.cmr.search_tools import normalize_tool_item
from util.langfuse import trace_update

logger = logging.getLogger(__name__)


@observe(name="get_tools")
def get_tools(  # pylint: disable=too-many-return-statements
    collection_concept_id: str | None = None,
    keyword: str | None = None,
    limit: LimitParam = 10,
    cursor: CursorParam = None,
    fields: FieldsParam = None,
) -> dict:
    """Search CMR tools for a single parent collection, returning all associated normalized results.

    The returned items use snake_cased keys that map directly to the UMM-T schema, including:
    - concept_id: CMR tool concept ID
    - native_id: The native ID of the tool record
    - revision_id: The revision ID of the tool metadata
    - provider_id: The provider ID of the tool
    - name: The name of the tool
    - long_name: The long name of the tool
    - type: The type of the tool (e.g. "Downloadable Tool")
    - version: The edition or version of the tool
    - description: A brief description of the tool
    - url: Primary endpoint URL information
    - related_urls: Documentation, guides, or other related links
    - access_constraints: Authentication or authorization requirements
    - use_constraints: Legal restrictions or usage limits
    - tool_keywords: Science or functional keywords describing the tool
    - organizations: Organizations associated with the tool
    - potential_action: Potential actions that can be performed with the tool
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
            fields=fields,
        )
    except (ValueError, TypeError) as exc:
        logger.warning("get_tools input validation failed: %s", exc)
        return GetToolsOutput(
            status=SearchStatus.ERROR,
            next_cursor=None,
            error_message=str(exc),
        ).model_dump()

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
            return GetToolsOutput(
                status=SearchStatus.ERROR,
                next_cursor=None,
                error_message=str(exc),
            ).model_dump()

    tool_ids: list[str] = []

    # Phase 1: Find linked tools. CMR collections only list the IDs of their associated
    # tools, not the full details. We first fetch the collection to get this list of IDs.
    if params.collection_concept_id:
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

        if not collection_page or not collection_page.items:
            return GetToolsOutput(status=SearchStatus.NO_RESULTS, next_cursor=None).model_dump()

        tool_ids = collection_page.items[0].get("meta", {}).get("associations", {}).get("tools", [])
        if not tool_ids and not params.keyword:
            return GetToolsOutput(status=SearchStatus.NO_RESULTS, next_cursor=None).model_dump()

    # Phase 2: Fetch the actual tool details using the IDs we found.
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

    if tool_page is None or not tool_page.items:
        return GetToolsOutput(status=SearchStatus.NO_RESULTS, next_cursor=None).model_dump()

    tools = [normalize_tool_item(item) for item in tool_page.items]
    next_cursor = (
        encode_cursor("cmr", tool_page.search_after)
        if tool_page.search_after and len(tool_page.items) == params.limit
        else None
    )
    response_dict = GetToolsOutput(
        status=SearchStatus.SUCCESS,
        tools=tools,
        total_hits=tool_page.total_hits,
        next_cursor=next_cursor,
    ).model_dump()

    if params.fields:
        apply_field_filter(response_dict["tools"], params.fields, MANDATORY_FIELDS_DEFAULT)

    return response_dict
