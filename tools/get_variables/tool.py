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

    When using the `keyword` argument, CMR searches across the following fields:
    - Variable Name and Long Name (e.g., "sea_surface_temperature" or "Sea Surface Temperature")
    - GCMD Science Keywords (e.g., broad categories like "Oceans" down to specific terms)
    - Variable Set Names (logical groupings of variables within a dataset)
    - Collection Concept IDs (the parent collection this variable belongs to)
    - Variable Concept ID (the unique CMR identifier for the variable)
    - Data Format (e.g., "NetCDF-4", "HDF5")

    This means you can discover variables using specific CF standard names, broad scientific
    categories, data formats, or by searching a parent collection's ID to find its variables.

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

    # Phase 1: Find linked variables. CMR collections only list the IDs of their associated
    # variables, not the full details. We first fetch the collection to get this list of variable IDs.
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

        # If the requested collection has no associated variables, the intersection
        # with any keyword is inherently empty. Return immediately.
        if not variable_ids and params.collection_concept_id:
            return GetVariablesOutput(status=SearchStatus.NO_RESULTS).model_dump()

    # Phase 2: Fetch the actual variable details. If both a collection ID and a keyword are
    # provided, CMR will only return variables that belong to that collection AND match the keyword.
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

    if params.collection_concept_id and params.keyword:
        # Compute count as intersection of collection-associated IDs and keyword results
        real_total_hits = len(
            [
                item
                for item in variable_page.items
                if item.get("meta", {}).get("concept-id") in variable_ids
            ]
        )
    elif params.collection_concept_id and variable_ids:
        # Just collection filter: the total is all associated variables
        real_total_hits = len(variable_ids)
    else:
        # Just keyword filter: rely on the search hit count
        real_total_hits = variable_page.total_hits

    return GetVariablesOutput(
        status=SearchStatus.SUCCESS,
        variables=variables,
        total_hits=real_total_hits,
    ).model_dump()
