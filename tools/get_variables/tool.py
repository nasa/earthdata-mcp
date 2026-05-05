"""Direct CMR variable search tool."""

import logging

from langfuse import observe

from models.tools.cmr_search import SearchStatus
from models.tools.get_variables import GetVariablesInput, GetVariablesOutput
from util.cmr.client import CMRError, search_cmr
from util.cmr.search_tools import normalize_variable_item
from util.langfuse import trace_update

logger = logging.getLogger(__name__)


@observe(name="get_variables")
def get_variables(
    collection_concept_id: str | None = None,
    keyword: str | None = None,
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
        )
    except (ValueError, TypeError) as exc:
        logger.warning("get_variables input validation failed: %s", exc)
        return GetVariablesOutput(
            status=SearchStatus.ERROR,
            error_message=str(exc),
        ).model_dump()

    variable_ids: list[str] = []

    # Phase 1: If collection_concept_id provided, fetch the collection to discover associations.
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
            return GetVariablesOutput(
                status=SearchStatus.ERROR,
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
                error_message="An unexpected internal error occurred during collection lookup.",
            ).model_dump()

        if not collection_page or not collection_page.items:
            return GetVariablesOutput(status=SearchStatus.NO_RESULTS).model_dump()

        variable_ids = (
            collection_page.items[0].get("meta", {}).get("associations", {}).get("variables", [])
        )

        # If no variables found and no fallback keyword provided, return immediately
        if not variable_ids and not params.keyword:
            return GetVariablesOutput(status=SearchStatus.NO_RESULTS).model_dump()

    # Phase 2: Fetch UMM-V records for the discovered variable concept IDs or direct keyword.
    search_params = {}
    if variable_ids:
        # Hard limit to 10 variables per the design requirement
        search_params["concept_id[]"] = variable_ids[:10]

    if params.keyword:
        search_params["keyword"] = params.keyword

    try:
        # Search variables endpoint.
        variable_page = next(
            search_cmr(
                concept_type="variable",
                search_params=search_params,
                page_size=10,
            ),
            None,
        )
    except (CMRError, ValueError, TypeError) as exc:
        logger.warning("Variable fetch failed for query %s: %s", search_params, exc)
        return GetVariablesOutput(
            status=SearchStatus.ERROR,
            error_message=str(exc),
        ).model_dump()
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.exception(
            "Unexpected error during variable fetch for query %s: %s", search_params, exc
        )
        return GetVariablesOutput(
            status=SearchStatus.ERROR,
            error_message="An unexpected internal error occurred during variable fetch.",
        ).model_dump()

    if variable_page is None or not variable_page.items:
        if variable_ids:
            logger.warning(
                "CMR returned no variables despite collection associations: %s", variable_ids
            )
        return GetVariablesOutput(status=SearchStatus.NO_RESULTS).model_dump()

    variables = [normalize_variable_item(item) for item in variable_page.items]

    # If we looked up via collection, the true total is the length of the associations list.
    real_total_hits = (
        len(variable_ids)
        if (params.collection_concept_id and variable_ids)
        else variable_page.total_hits
    )

    return GetVariablesOutput(
        status=SearchStatus.SUCCESS,
        variables=variables,
        total_hits=real_total_hits,
    ).model_dump()
