"""Pagination types, utilities, and mandatory field sets."""

from typing import Annotated

from pydantic import Field

LimitParam = Annotated[
    int,
    Field(
        default=10,
        description=(
            "Maximum number of results to return (default 10, max 50). "
            "Keep this small to avoid context window bloat. "
            "When using limit > 10, always specify the fields parameter."
        ),
    ),
]

CursorParam = Annotated[
    str | None,
    Field(
        default=None,
        description=(
            "Pagination token for the next page of results. "
            "Pass the exact next_cursor string returned by the previous tool call. "
            "Cursors are query-scoped: they lock in the original search parameters "
            "and cannot be reused across different tools or different queries. "
            "If you need to change any search parameter, start a new search without a cursor."
        ),
    ),
]

FieldsParam = Annotated[
    list[str],
    Field(
        default_factory=list,
        description=(
            "Strongly recommended. Pass an array of top-level keys to include per result item "
            "(e.g., ['concept_id', 'entry_title', 'abstract']) to aggressively reduce payload size "
            "and preserve context window. CMR responses are highly verbose — omitting this parameter "
            "when fetching more than a few results will bloat your context. "
            "concept_id is always returned regardless of what is specified here."
        ),
    ),
]

# get_collections serializes as entry_title, not name
MANDATORY_FIELDS_COLLECTIONS: frozenset[str] = frozenset({"concept_id", "entry_title"})

# get_granules serializes as granule_ur, not name
MANDATORY_FIELDS_GRANULES: frozenset[str] = frozenset({"concept_id", "granule_ur"})

# All other CMR tools (citations, services, tools, variables)
MANDATORY_FIELDS_DEFAULT: frozenset[str] = frozenset({"concept_id", "name"})
