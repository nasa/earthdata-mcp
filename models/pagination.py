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
            "Do not modify, reconstruct, or reuse cursors across different tools."
        ),
    ),
]

FieldsParam = Annotated[
    list[str] | None,
    Field(
        default=None,
        description=(
            "Specific top-level keys to include per result item "
            "(e.g., ['concept_id', 'entry_title', 'abstract']). "
            "Use to reduce payload size. concept_id is always returned regardless."
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
