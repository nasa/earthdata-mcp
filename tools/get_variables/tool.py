"""Direct CMR variable search tool."""

import logging

from langfuse import observe

from models.pagination import (
    MANDATORY_FIELDS_DEFAULT,
    CursorParam,
    LimitParam,
)
from models.tools.cmr_search import SearchStatus
from models.tools.get_variables import GetVariablesInput, GetVariablesOutput
from util.cmr.client import CMRError, search_cmr
from util.cmr.search_tools import fetch_association_ids, normalize_variable_item
from util.langfuse import trace_update
from util.pagination import apply_field_filter, encode_cursor, resolve_cursor

logger = logging.getLogger(__name__)


@observe(name="get_variables")
def get_variables(
    collection_concept_id: str | None = None,
    keyword: str | None = None,
    limit: LimitParam = 10,
    cursor: CursorParam = None,
    fields: list[str] | None = None,
) -> dict:
    # pylint: disable=too-many-return-statements
    """Search CMR variables by parent collection ID or keyword.

    The returned items use snake_cased keys mapping to UMM-V, including:
    - concept_id: CMR variable concept ID
    - name: Variable short name
    - long_name: Variable long name
    - definition: Variable definition
    - data_type: Data type of the variable
    - units: Units of measurement
    - scale: Scale factor
    - offset: Offset value
    - fill_values: Values indicating missing or invalid data
    - valid_ranges: Valid data ranges
    - dimensions: Variable dimensions
    - standard_name: The CF Standard Name
    - science_keywords: GCMD Science Keywords
    - variable_type: Type of variable
    - variable_sub_type: Sub-type of variable
    - sets: Logical groupings
    - measurement_identifiers: Measurement context
    - sampling_identifiers: Sampling method context
    - related_urls: Specific URLs

    Pagination: use limit (default 10, max 50) and cursor to page through results.
    Pass the next_cursor from a previous response as cursor to advance to the next page.
    Cursors are query-scoped: they lock in the original search parameters and cannot be reused
    across different tools or different queries. To change search parameters, start a new search
    without a cursor.
    """
    trace_update(
        tags=["cmr", "variables"],
        metadata={
            "collection_concept_id": collection_concept_id,
            "keyword": keyword,
        },
    )

    try:
        params = GetVariablesInput(
            collection_concept_id=collection_concept_id,
            keyword=keyword,
            limit=limit,
            cursor=cursor,
            fields=fields or [],
        )
    except (ValueError, TypeError) as exc:
        logger.warning("get_variables input validation failed: %s", exc)
        return GetVariablesOutput(
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
                return GetVariablesOutput(
                    status=SearchStatus.ERROR,
                    error_message="Cursor parameters are query-scoped. You cannot change search parameters when paginating.",
                    next_cursor=None,
                ).model_dump()
        except ValueError as exc:
            return GetVariablesOutput(
                status=SearchStatus.ERROR,
                next_cursor=None,
                error_message=str(exc),
            ).model_dump()

    variable_ids: list[str] = []

    if search_params is None:
        # Phase 1: If collection_concept_id provided, fetch the collection to discover associations.
        if params.collection_concept_id:
            try:
                found_ids = fetch_association_ids(params.collection_concept_id, "variables")
            except (CMRError, ValueError, TypeError) as exc:
                logger.warning(
                    "Collection lookup failed for %s: %s", params.collection_concept_id, exc
                )
                return GetVariablesOutput(
                    status=SearchStatus.ERROR,
                    next_cursor=None,
                    error_message=str(exc),
                ).model_dump()
            except Exception as exc:  # pylint: disable=broad-exception-caught
                logger.exception(
                    "Unexpected error during collection lookup for %s: %s",
                    params.collection_concept_id,
                    exc,
                )
                return GetVariablesOutput(
                    status=SearchStatus.ERROR,
                    next_cursor=None,
                    error_message="An unexpected internal error occurred during collection lookup.",
                ).model_dump()

            if found_ids is None:
                return GetVariablesOutput(
                    status=SearchStatus.NO_RESULTS, next_cursor=None
                ).model_dump()
            variable_ids = found_ids
            if not variable_ids and not params.keyword:
                return GetVariablesOutput(
                    status=SearchStatus.NO_RESULTS, next_cursor=None
                ).model_dump()

        # Phase 2 params: build from Phase 1 results or direct keyword.
        search_params = {}
        if variable_ids:
            search_params["concept_id[]"] = variable_ids

        if params.keyword:
            search_params["keyword"] = params.keyword

    try:
        variable_page = next(
            search_cmr(
                concept_type="variable",
                search_params=search_params,
                page_size=params.limit,
                search_after=search_after,
            ),
            None,
        )
    except (CMRError, ValueError, TypeError) as exc:
        logger.warning("Variable fetch failed for query %s: %s", search_params, exc)
        return GetVariablesOutput(
            status=SearchStatus.ERROR,
            next_cursor=None,
            error_message=str(exc),
        ).model_dump()
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.exception(
            "Unexpected error during variable fetch for query %s: %s", search_params, exc
        )
        return GetVariablesOutput(
            status=SearchStatus.ERROR,
            next_cursor=None,
            error_message="An unexpected internal error occurred during variable fetch.",
        ).model_dump()

    if variable_page is None or not variable_page.items:
        if variable_ids:
            logger.warning(
                "CMR returned no variables despite collection associations: %s", variable_ids
            )
        return GetVariablesOutput(status=SearchStatus.NO_RESULTS, next_cursor=None).model_dump()

    variables = [normalize_variable_item(item) for item in variable_page.items]
    cursor_payload = {
        "token": variable_page.search_after,
        "params": search_params,
        "inputs": current_inputs,
    }
    next_cursor = (
        encode_cursor("cmr", cursor_payload)
        if variable_page.search_after and len(variable_page.items) == params.limit
        else None
    )

    response_dict = GetVariablesOutput(
        status=SearchStatus.SUCCESS,
        variables=variables,
        total_hits=variable_page.total_hits,
        next_cursor=next_cursor,
    ).model_dump()

    if params.fields:
        apply_field_filter(response_dict["variables"], params.fields, MANDATORY_FIELDS_DEFAULT)

    return response_dict
