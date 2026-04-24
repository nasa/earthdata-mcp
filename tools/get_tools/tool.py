"""Direct CMR tool search tool."""

import logging

from langfuse import observe

from models.tools.cmr_search import SearchStatus
from models.tools.get_tools import (
    CollectionConceptIdParam,
    GetToolsInput,
    GetToolsOutput,
)
from util.cmr.client import CMRError, search_cmr
from util.cmr.search_tools import normalize_tool_item
from util.langfuse import trace_update

logger = logging.getLogger(__name__)


@observe(name="get_tools")
def get_tools(  # pylint: disable=too-many-return-statements
    collection_concept_id: CollectionConceptIdParam,
) -> dict:
    """Search CMR tools for a single parent collection, returning all associated normalized results.

    The returned items use snake_cased keys that map directly to the UMM-T schema, including:
    - concept_id: CMR tool concept ID
    - native_id: The native ID of the tool record
    - revision_id: The revision ID of the tool metadata
    - provider_id: The provider ID of the tool
    - name: The name of the tool
    - long_name: The long name of the tool
    - type: The type of the tool (e.g., Downloadable Tool, Web User Interface, Web Portal, Model)
    - version: The edition or version of the tool
    - description: A brief description of the tool
    - url: Primary URL for accessing the tool
    - doi: Digital Object Identifier of the tool
    - related_urls: Documentation, guides, or other related links
    - supported_input_formats: File formats the tool can read
    - supported_output_formats: File formats the tool can produce
    - supported_operating_systems: OS compatibility
    - supported_browsers: Browser compatibility
    - supported_software_languages: Programming language compatibility
    - tool_keywords: Earth science keywords for the tool
    - organizations: Providers, developers, or publishers
    - quality: Quality information
    - access_constraints: Constraints for accessing the tool
    - use_constraints: Restrictions or limitations on use
    - potential_action: Smart handoff definition for parameterized deep links
    """
    trace_update(
        tags=["cmr", "tools"],
        metadata={
            "collection_concept_id": collection_concept_id,
        },
    )

    try:
        params = GetToolsInput(collection_concept_id=collection_concept_id)
    except (ValueError, TypeError) as exc:
        logger.warning("get_tools input validation failed: %s", exc)
        return GetToolsOutput(
            status=SearchStatus.ERROR,
            error_message=str(exc),
        ).model_dump()

    # Phase 1: fetch the collection record to discover its direct tool associations.
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
            error_message=str(exc),
        ).model_dump()
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception(
            "Unexpected error during collection lookup for %s",
            params.collection_concept_id,
        )
        return GetToolsOutput(
            status=SearchStatus.ERROR,
            error_message="An unexpected internal error occurred during collection lookup.",
        ).model_dump()

    if not collection_page or not collection_page.items:
        return GetToolsOutput(status=SearchStatus.NO_RESULTS).model_dump()

    tool_ids: list[str] = (
        collection_page.items[0].get("meta", {}).get("associations", {}).get("tools", [])
    )
    if not tool_ids:
        return GetToolsOutput(status=SearchStatus.NO_RESULTS).model_dump()

    # Phase 2: fetch UMM-T records for the discovered tool concept IDs.
    try:
        tool_page = next(
            search_cmr(
                concept_type="tool",
                search_params={"concept_id[]": tool_ids},
                page_size=2000,
            ),
            None,
        )
    except (CMRError, ValueError, TypeError) as exc:
        logger.warning("Tool fetch failed for collection %s: %s", params.collection_concept_id, exc)
        return GetToolsOutput(
            status=SearchStatus.ERROR,
            error_message=str(exc),
        ).model_dump()
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception("Unexpected error during tool fetch for %s", params.collection_concept_id)
        return GetToolsOutput(
            status=SearchStatus.ERROR,
            error_message="An unexpected internal error occurred during tool fetch.",
        ).model_dump()

    if tool_page is None:
        return GetToolsOutput(status=SearchStatus.NO_RESULTS).model_dump()

    tools = [normalize_tool_item(item) for item in tool_page.items]
    status = SearchStatus.SUCCESS if tools else SearchStatus.NO_RESULTS
    return GetToolsOutput(
        status=status,
        tools=tools,
        total_hits=tool_page.total_hits,
    ).model_dump()
