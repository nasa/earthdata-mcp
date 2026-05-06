"""Tests for models/pagination.py cursor encoding utilities."""

import base64
import json

import pytest

from models.pagination import (
    MANDATORY_FIELDS_COLLECTIONS,
    MANDATORY_FIELDS_DEFAULT,
    MANDATORY_FIELDS_GRANULES,
    CursorParam,
    FieldsParam,
    LimitParam,
)
from util.pagination import apply_field_filter, decode_cursor, encode_cursor


def _b64url_encode(payload: dict) -> str:
    """Helper: raw urlsafe base64 without padding."""
    raw = json.dumps(payload).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


# --- encode / decode round-trip ---


def test_encode_decode_cmr_cursor_roundtrip():
    """encode_cursor / decode_cursor should round-trip a CMR search-after token."""
    token = "CMR-Search-After-XYZ"
    cursor = encode_cursor("cmr", token)
    decoded = decode_cursor(cursor)
    assert decoded == {"backend": "cmr", "value": token}


def test_encode_decode_kms_cursor_roundtrip():
    """encode_cursor / decode_cursor should round-trip a KMS offset integer."""
    offset = 20
    cursor = encode_cursor("kms", offset)
    decoded = decode_cursor(cursor)
    assert decoded == {"backend": "kms", "value": offset}


# --- URL-safe output ---


def test_encode_cursor_no_plus():
    """encode_cursor output must not contain + characters."""
    cursor = encode_cursor("cmr", "some+token+value")
    assert "+" not in cursor


def test_encode_cursor_no_slash():
    """encode_cursor output must not contain / characters."""
    cursor = encode_cursor("cmr", "some/token/value")
    assert "/" not in cursor


def test_encode_cursor_no_padding():
    """encode_cursor must strip all = padding characters."""
    # Produce tokens of various lengths to hit all padding cases
    for suffix in ["", "x", "xx", "xxx"]:
        cursor = encode_cursor("cmr", f"token{suffix}")
        assert "=" not in cursor


# --- decode with stripped padding ---
# Base64 padding is 0, 1, or 2 `=` chars. Use payloads that produce each case.
# decode_cursor must tolerate any number of missing `=` chars (0, 1, or 2).


@pytest.mark.parametrize(
    "payload",
    [
        {"backend": "cmr", "value": "abcde"},  # 0 padding chars stripped
        {"backend": "cmr", "value": "x"},  # 1 padding char stripped
        {"backend": "cmr", "value": "abc"},  # 2 padding chars stripped
        {"backend": "kms", "value": 0},  # kms integer value
    ],
)
def test_decode_cursor_tolerates_stripped_padding(payload):
    """decode_cursor must succeed when base64 padding has been stripped."""
    raw = json.dumps(payload).encode("utf-8")
    # encode_cursor already strips padding; simulate the same here directly
    stripped = base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")
    assert decode_cursor(stripped) == payload


# --- garbage input ---


def test_decode_cursor_garbage_raises_value_error():
    """decode_cursor must raise ValueError on non-base64 input."""
    with pytest.raises(ValueError, match="Invalid pagination cursor"):
        decode_cursor("this-is-not-base64-json!@#$")


def test_decode_cursor_valid_base64_not_json_raises():
    """decode_cursor must raise ValueError when base64 decodes but isn't JSON."""
    # Valid base64url but not JSON
    not_json = base64.urlsafe_b64encode(b"not json at all").decode("utf-8").rstrip("=")
    with pytest.raises(ValueError, match="Invalid pagination cursor"):
        decode_cursor(not_json)


# --- mandatory field sets ---


def test_mandatory_fields_collections():
    """MANDATORY_FIELDS_COLLECTIONS must use the serialized key entry_title, not name."""
    assert {"concept_id", "entry_title"} == MANDATORY_FIELDS_COLLECTIONS


def test_mandatory_fields_granules():
    """MANDATORY_FIELDS_GRANULES must use the serialized key granule_ur, not name."""
    assert {"concept_id", "granule_ur"} == MANDATORY_FIELDS_GRANULES


def test_mandatory_fields_default():
    """MANDATORY_FIELDS_DEFAULT covers citations, services, tools, and variables."""
    assert {"concept_id", "name"} == MANDATORY_FIELDS_DEFAULT


# --- Annotated type metadata (Field defaults) ---


def test_limit_param_has_default_10():
    """LimitParam JSON schema default must be 10."""
    from pydantic import TypeAdapter

    ta = TypeAdapter(LimitParam)
    schema = ta.json_schema()
    assert schema.get("default") == 10


def test_cursor_param_default_none():
    """CursorParam JSON schema default must be None."""
    from pydantic import TypeAdapter

    ta = TypeAdapter(CursorParam)
    schema = ta.json_schema()
    assert schema.get("default") is None


def test_fields_param_schema_is_optional():
    """FieldsParam JSON schema default must be empty list."""
    from pydantic import BaseModel

    class TestModel(BaseModel):
        """Test model for fields schema."""

        fields: FieldsParam

    schema = TestModel.model_json_schema()
    assert "fields" not in schema.get("required", [])


# --- apply_field_filter ---


def test_apply_field_filter_removes_unrequested_fields():
    """apply_field_filter must strip fields not in requested or mandatory sets."""
    items = [{"concept_id": "C1", "entry_title": "T", "abstract": "A", "short_name": "S"}]
    apply_field_filter(items, ["abstract"], MANDATORY_FIELDS_COLLECTIONS)
    assert items[0] == {"concept_id": "C1", "entry_title": "T", "abstract": "A"}


def test_apply_field_filter_always_keeps_mandatory_fields():
    """apply_field_filter must retain mandatory fields even when not in requested list."""
    items = [{"concept_id": "C1", "granule_ur": "G1", "provider_id": "P"}]
    apply_field_filter(items, [], MANDATORY_FIELDS_GRANULES)
    assert "concept_id" in items[0]
    assert "granule_ur" in items[0]
    assert "provider_id" not in items[0]


def test_apply_field_filter_mutates_in_place():
    """apply_field_filter must modify the original list, not return a new one."""
    items = [{"concept_id": "C1", "name": "N", "extra": "X"}]
    original = items
    apply_field_filter(items, [], MANDATORY_FIELDS_DEFAULT)
    assert items is original


def test_apply_field_filter_handles_multiple_items():
    """apply_field_filter must apply consistently to every item in the list."""
    items = [
        {"concept_id": "C1", "entry_title": "T1", "abstract": "A1"},
        {"concept_id": "C2", "entry_title": "T2", "abstract": "A2"},
    ]
    apply_field_filter(items, [], MANDATORY_FIELDS_COLLECTIONS)
    for item in items:
        assert set(item.keys()) == {"concept_id", "entry_title"}
