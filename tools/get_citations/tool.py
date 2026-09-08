"""Direct CMR citation search tool."""

import logging

from langfuse import observe

from models.pagination import (
    MANDATORY_FIELDS_DEFAULT,
    CursorParam,
    LimitParam,
)
from models.tools.cmr_search import SearchStatus
from models.tools.get_citations import GetCitationsInput, GetCitationsOutput
from util.cmr.client import CMRError, search_cmr
from util.cmr.search_tools import fetch_association_ids, normalize_citation_item
from util.langfuse import trace_update
from util.pagination import apply_field_filter, encode_cursor, resolve_cursor

logger = logging.getLogger(__name__)


@observe(name="get_citations")
def get_citations(  # pylint: disable=too-many-return-statements
    collection_concept_id: str | None = None,
    identifier: str | None = None,
    provider: str | None = None,
    limit: LimitParam = 10,
    cursor: CursorParam = None,
    fields: list[str] | None = None,
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

    Pagination: use limit (default 10, max 50) and cursor to page through results.
    Pass the next_cursor from a previous response as cursor to advance to the next page.
    Cursors are query-scoped: they lock in the original search parameters and cannot be reused
    across different tools or different queries. To change search parameters, start a new search
    without a cursor.
    """
    trace_update(
        tags=["cmr", "citations"],
        metadata={
            "collection_concept_id": collection_concept_id,
            "identifier": identifier,
            "provider": provider,
        },
    )

    try:
        params = GetCitationsInput(
            collection_concept_id=collection_concept_id,
            identifier=identifier,
            provider=provider,
            limit=limit,
            cursor=cursor,
            fields=fields or [],
        )
    except (ValueError, TypeError) as exc:
        logger.warning("get_citations input validation failed: %s", exc)
        return GetCitationsOutput(
            status=SearchStatus.ERROR,
            next_cursor=None,
            error_message=str(exc),
        ).model_dump()

    search_after = None
    search_params = None  # sentinel: None means "must build via Phase 1"

    # Build input representation for cursor comparison
    current_inputs = {
        "collection_concept_id": params.collection_concept_id,
        "identifier": params.identifier,
        "provider": params.provider,
    }

    if params.cursor:
        try:
            cursor_value = resolve_cursor(params.cursor, "cmr")
            search_after = cursor_value.get("token")
            search_params = cursor_value.get("params", {})
            cursor_inputs = cursor_value.get("inputs", {})

            # Compare inputs instead of search_params to avoid slow Phase 1 on page 2
            normalized_search = {k: v for k, v in current_inputs.items() if v}
            for k, v in normalized_search.items():
                if isinstance(v, list):
                    normalized_search[k] = sorted(v)

            normalized_cursor = {k: v for k, v in cursor_inputs.items() if v}
            for k, v in normalized_cursor.items():
                if isinstance(v, list):
                    normalized_cursor[k] = sorted(v)

            if normalized_search != normalized_cursor:
                return GetCitationsOutput(
                    status=SearchStatus.ERROR,
                    error_message="Cursor parameters are query-scoped. You cannot change search parameters when paginating.",
                    next_cursor=None,
                ).model_dump()
        except ValueError as exc:
            return GetCitationsOutput(
                status=SearchStatus.ERROR,
                next_cursor=None,
                error_message=str(exc),
            ).model_dump()

    citation_ids: list[str] = []

    if search_params is None:
        # Phase 1: If collection_concept_id provided, fetch the collection to discover associations.
        if params.collection_concept_id:
            try:
                found_ids = fetch_association_ids(params.collection_concept_id, "citations")
            except (CMRError, ValueError, TypeError) as exc:
                logger.warning(
                    "Collection lookup failed for %s: %s", params.collection_concept_id, exc
                )
                return GetCitationsOutput(
                    status=SearchStatus.ERROR,
                    next_cursor=None,
                    error_message=str(exc),
                ).model_dump()
            except Exception:  # pylint: disable=broad-exception-caught
                logger.exception(
                    "Unexpected error during collection lookup for %s",
                    params.collection_concept_id,
                )
                return GetCitationsOutput(
                    status=SearchStatus.ERROR,
                    next_cursor=None,
                    error_message="An unexpected internal error occurred during collection lookup.",
                ).model_dump()

            if not found_ids:
                return GetCitationsOutput(
                    status=SearchStatus.NO_RESULTS, next_cursor=None
                ).model_dump()
            citation_ids = found_ids

        # Phase 2 params: build from Phase 1 results or direct identifier.
        search_params = {}
        if citation_ids:
            search_params["concept_id[]"] = citation_ids

        if params.identifier:
            search_params["identifier"] = params.identifier

        if params.provider:
            search_params["provider"] = params.provider

    try:
        citation_page = next(
            search_cmr(
                concept_type="citation",
                search_params=search_params,
                page_size=params.limit,
                search_after=search_after,
            ),
            None,
        )
    except (CMRError, ValueError, TypeError) as exc:
        logger.warning("Citation fetch failed for query %s: %s", search_params, exc)
        return GetCitationsOutput(
            status=SearchStatus.ERROR,
            next_cursor=None,
            error_message=str(exc),
        ).model_dump()
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception("Unexpected error during citation fetch for query %s", search_params)
        return GetCitationsOutput(
            status=SearchStatus.ERROR,
            next_cursor=None,
            error_message="An unexpected internal error occurred during citation fetch.",
        ).model_dump()

    if citation_page is None or not citation_page.items:
        if citation_ids:
            logger.warning(
                "CMR returned no citations despite collection associations: %s", citation_ids
            )
        return GetCitationsOutput(status=SearchStatus.NO_RESULTS, next_cursor=None).model_dump()

    citations = [normalize_citation_item(item) for item in citation_page.items]
    cursor_payload = {
        "token": citation_page.search_after,
        "params": search_params,
        "inputs": current_inputs,
    }
    next_cursor = (
        encode_cursor("cmr", cursor_payload)
        if citation_page.search_after and len(citation_page.items) == params.limit
        else None
    )
    if search_after is None and params.collection_concept_id:
        real_total_hits = len(citation_ids) if citation_ids else citation_page.total_hits
    else:
        real_total_hits = citation_page.total_hits

    response_dict = GetCitationsOutput(
        status=SearchStatus.SUCCESS,
        citations=citations,
        total_hits=real_total_hits,
        next_cursor=next_cursor,
    ).model_dump()

    if params.fields:
        apply_field_filter(response_dict["citations"], params.fields, MANDATORY_FIELDS_DEFAULT)

    return response_dict
