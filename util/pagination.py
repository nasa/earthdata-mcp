"""Pagination utilities for encoding, decoding, and filtering."""

import base64
import json
from typing import Any


def encode_cursor(backend: str, value: Any) -> str:
    """Encode a pagination cursor as a URL-safe base64 string with no padding."""
    payload = json.dumps({"backend": backend, "value": value})
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("utf-8").rstrip("=")


def decode_cursor(cursor: str) -> dict[str, Any]:
    """Decode a pagination cursor, re-adding stripped base64 padding as needed."""
    try:
        # Base64 requires length to be a multiple of 4; pad with '=' if needed

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
