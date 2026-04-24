"""Direct CMR citation search tool."""

import logging

from langfuse import observe

from models.tools.cmr_search import SearchStatus
from models.tools.get_citations import GetCitationsInput, GetCitationsOutput
from util.cmr.client import CMRError, search_cmr
from util.cmr.search_tools import normalize_citation_item
from util.langfuse import trace_update

logger = logging.getLogger(__name__)


@observe(name="get_citations")
def get_citations(  # pylint: disable=too-many-return-statements
    collection_concept_id: str | None = None,
    identifier: str | None = None,
) -> dict:
    """Search CMR citations by parent collection ID or specific citation identifier (DOI).

    CRITICAL: You must provide EXACTLY ONE of `collection_concept_id` or `identifier`.

    The returned items use snake_cased keys mapping to UMM-Citations, including:
    - concept_id: CMR citation concept ID
    - name: The name or title of the citation
    - identifier: The primary DOI or identifier
    - identifier_type: The type of the identifier (e.g. DOI)
    - abstract: A brief abstract or description
    - citation_metadata: Rich nested metadata including Author, Year, Publisher, etc.
    - related_identifiers: List of related works or data (e.g. Cites, Refers)
    """
    trace_update(
        tags=["cmr", "citations"],
        metadata={
            "collection_concept_id": collection_concept_id,
            "identifier": identifier,
        },
    )

    try:
        params = GetCitationsInput(
            collection_concept_id=collection_concept_id,
            identifier=identifier,
        )
    except (ValueError, TypeError) as exc:
        logger.warning("get_citations input validation failed: %s", exc)
        return GetCitationsOutput(
            status=SearchStatus.ERROR,
            error_message=str(exc),
        ).model_dump()

    citation_ids: list[str] = []

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
            return GetCitationsOutput(
                status=SearchStatus.ERROR,
                error_message=str(exc),
            ).model_dump()
        except Exception:  # pylint: disable=broad-exception-caught
            logger.exception(
                "Unexpected error during collection lookup for %s",
                params.collection_concept_id,
            )
            return GetCitationsOutput(
                status=SearchStatus.ERROR,
                error_message="An unexpected internal error occurred during collection lookup.",
            ).model_dump()

        if not collection_page or not collection_page.items:
            return GetCitationsOutput(status=SearchStatus.NO_RESULTS).model_dump()

        citation_ids = (
            collection_page.items[0].get("meta", {}).get("associations", {}).get("citations", [])
        )

        # If no citations found on the collection, return immediately
        if not citation_ids:
            return GetCitationsOutput(status=SearchStatus.NO_RESULTS).model_dump()

    # Phase 2: Fetch UMM-C records for the discovered citation concept IDs or direct identifier.
    search_params = {}
    if citation_ids:
        # Hard limit to 10 citations per the design requirement
        search_params["concept_id[]"] = citation_ids[:10]

    if params.identifier:
        search_params["identifier"] = params.identifier

    # If we somehow reached here with no search parameters, we have nothing to search for.
    try:
        citation_page = next(
            search_cmr(
                concept_type="citation",
                search_params=search_params,
                page_size=10,
            ),
            None,
        )
    except (CMRError, ValueError, TypeError) as exc:
        logger.warning("Citation fetch failed for query %s: %s", search_params, exc)
        return GetCitationsOutput(
            status=SearchStatus.ERROR,
            error_message=str(exc),
        ).model_dump()
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception("Unexpected error during citation fetch for query %s", search_params)
        return GetCitationsOutput(
            status=SearchStatus.ERROR,
            error_message="An unexpected internal error occurred during citation fetch.",
        ).model_dump()

    if citation_page is None or not citation_page.items:
        if citation_ids:
            logger.warning(
                "CMR returned no citations despite collection associations: %s", citation_ids
            )
        return GetCitationsOutput(status=SearchStatus.NO_RESULTS).model_dump()

    citations = [normalize_citation_item(item) for item in citation_page.items]

    # If we looked up via collection, the true total is the length of the associations list.
    # Because we sliced to 10 for the fetch, CMR will only report up to 10 hits.
    real_total_hits = (
        len(citation_ids) if params.collection_concept_id else citation_page.total_hits
    )

    return GetCitationsOutput(
        status=SearchStatus.SUCCESS,
        citations=citations,
        total_hits=real_total_hits,
    ).model_dump()
