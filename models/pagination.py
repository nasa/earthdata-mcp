"""Pagination types, utilities, and mandatory field sets."""

import base64
import json
from typing import Annotated, Any

from pydantic import Field

LimitParam = Annotated[
    int,
    Field(
        default=10,
        le=50,
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
    list[str] | None,
    Field(
        default=None,
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


def encode_cursor(backend: str, value: Any) -> str:
    """Encode a pagination cursor as a URL-safe base64 string with no padding."""
    payload = json.dumps({"backend": backend, "value": value})
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("utf-8").rstrip("=")


def decode_cursor(cursor: str) -> dict[str, Any]:
    """Decode a pagination cursor, re-adding stripped base64 padding as needed."""
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        payload = base64.urlsafe_b64decode(padded).decode("utf-8")
        return json.loads(payload)
    except Exception as e:
        raise ValueError(f"Invalid pagination cursor: {e}") from e


def resolve_cursor(cursor: str, backend: str) -> dict[str, Any]:
    """Decode and validate a pagination cursor, returning the inner value dict.

    Raises ValueError with standard user-facing messages on backend mismatch or
    outdated scalar format. Callers extract token/params/offset/etc. from the result.
    """
    parsed = decode_cursor(cursor)
    if parsed.get("backend") != backend:
        raise ValueError(
            "Cursor is not valid for this tool. Cursors cannot be reused across "
            "different tools. Start a new search without a cursor parameter."
        )
    cursor_value = parsed.get("value")
    if not isinstance(cursor_value, dict):
        raise ValueError("Cursor format is outdated. Please start a new search without a cursor.")
    return cursor_value


def apply_field_filter(
    items: list[dict[str, Any]],
    fields: list[str],
    mandatory: frozenset[str],
) -> None:
    """Filter item dicts in-place, keeping only requested fields plus mandatory ones."""
    requested = set(fields)
    for item in items:
        keys_to_remove = [k for k in item if k not in requested and k not in mandatory]
        for k in keys_to_remove:
            del item[k]
