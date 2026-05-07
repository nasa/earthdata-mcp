"""Direct KMS keyword search tool."""

import logging

import requests
from langfuse import observe

from models.pagination import (
    CursorParam,
    LimitParam,
)
from models.tools.cmr_search import SearchStatus
from models.tools.get_keywords import GetKeywordsInput, GetKeywordsOutput, KeywordResult
from util.kms.client import search_kms_pattern
from util.langfuse import trace_update
from util.pagination import apply_field_filter, encode_cursor, resolve_cursor

logger = logging.getLogger(__name__)

_MANDATORY_FIELDS = frozenset({"uuid"})


@observe(name="get_keywords")
def get_keywords(  # pylint: disable=too-many-return-statements
    query: str,
    scheme: str | None = None,
    limit: LimitParam = 10,
    cursor: CursorParam = None,
    fields: list[str] | None = None,
) -> dict:
    """Search NASA's Keyword Management System (KMS) for vocabulary terms.

    This tool performs a live pattern search against the KMS API and extracts
    the preferred labels and definitions. These terms are highly useful for
    constructing accurate searches using the get_collections tool.

    Pagination: KMS returns all matching concepts in one response; slicing is
    performed in-memory. total_hits always reflects the full result count.
    Pass the returned next_cursor into cursor to advance to the next page.
    Cursors are query-scoped: they lock in the original search parameters and cannot be reused
    across different tools or different queries. To change search parameters, start a new search
    without a cursor.
    """
    trace_update(
        tags=["kms", "keywords"],
        metadata={
            "query": query,
            "scheme": scheme,
        },
    )

    try:
        params = GetKeywordsInput(
            query=query,
            scheme=scheme,
            limit=limit,
            cursor=cursor,
            fields=fields or [],
        )
    except (ValueError, TypeError) as exc:
        logger.warning("get_keywords input validation failed: %s", exc)
        return GetKeywordsOutput(
            status=SearchStatus.ERROR,
            total_hits=0,
            next_cursor=None,
            error_message=str(exc),
            keywords=[],
        ).model_dump()

    offset = 0
    query = params.query
    scheme = params.scheme
    if params.cursor:
        try:
            cursor_value = resolve_cursor(params.cursor, "kms")
            offset = cursor_value.get("offset", 0)
            cursor_query = cursor_value.get("query")
            cursor_scheme = cursor_value.get("scheme")

            if (cursor_query and cursor_query != params.query) or (cursor_scheme != params.scheme):
                return GetKeywordsOutput(
                    status=SearchStatus.ERROR,
                    total_hits=0,
                    next_cursor=None,
                    error_message="Cursor parameters are query-scoped. You cannot change search parameters when paginating.",
                    keywords=[],
                ).model_dump()

            query = cursor_query or params.query
            scheme = cursor_scheme or params.scheme

        except ValueError as exc:
            return GetKeywordsOutput(
                status=SearchStatus.ERROR,
                total_hits=0,
                next_cursor=None,
                error_message=str(exc),
                keywords=[],
            ).model_dump()

    try:
        raw_concepts = search_kms_pattern(query, scheme)
    except requests.RequestException as exc:
        logger.error("Failed to fetch KMS keywords: %s", exc)
        return GetKeywordsOutput(
            status=SearchStatus.ERROR,
            total_hits=0,
            next_cursor=None,
            error_message=f"Failed to communicate with KMS API: {exc}",
            keywords=[],
        ).model_dump()
    except (ValueError, TypeError) as exc:
        logger.warning("KMS keyword fetch failed: %s", exc)
        return GetKeywordsOutput(
            status=SearchStatus.ERROR,
            total_hits=0,
            next_cursor=None,
            error_message=str(exc),
            keywords=[],
        ).model_dump()
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.exception("Unexpected error in get_keywords for query '%s': %s", params.query, exc)
        return GetKeywordsOutput(
            status=SearchStatus.ERROR,
            total_hits=0,
            next_cursor=None,
            error_message="An unexpected error occurred while processing KMS keywords.",
            keywords=[],
        ).model_dump()

    if not raw_concepts:
        return GetKeywordsOutput(
            status=SearchStatus.NO_RESULTS,
            total_hits=0,
            next_cursor=None,
            error_message=None,
            keywords=[],
        ).model_dump()

    total_hits = len(raw_concepts)
    page_concepts = raw_concepts[offset : offset + params.limit]
    next_cursor = (
        encode_cursor("kms", {"offset": offset + params.limit, "query": query, "scheme": scheme})
        if offset + params.limit < total_hits
        else None
    )

    keywords = []
    for concept in page_concepts:
        definition_text = None
        if (
            concept.get("definitions")
            and isinstance(concept["definitions"], list)
            and isinstance(concept["definitions"][0], dict)
        ):
            definition_text = concept["definitions"][0].get("text")

        concept_scheme = concept.get("scheme", {})
        if not isinstance(concept_scheme, dict):
            concept_scheme = {}

        keywords.append(
            KeywordResult(
                uuid=concept.get("uuid", ""),
                prefLabel=concept.get("prefLabel", ""),
                scheme=concept_scheme,
                definition=definition_text,
            )
        )

    response_dict = GetKeywordsOutput(
        status=SearchStatus.SUCCESS,
        total_hits=total_hits,
        next_cursor=next_cursor,
        error_message=None,
        keywords=keywords,
    ).model_dump()

    if params.fields:
        apply_field_filter(response_dict["keywords"], params.fields, _MANDATORY_FIELDS)

    return response_dict
