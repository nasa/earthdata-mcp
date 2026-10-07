"""Keep UMM-G instantaneous acquisition times in granule search results."""

from copy import deepcopy
from datetime import UTC, datetime

import pytest
import responses

from util.cmr.client import CMR_URL
from util.cmr.search_tools import extract_granule_temporal_extent, normalize_granule_item


@pytest.mark.parametrize(
    "value, expected",
    [
        ("2026-09-01T12:30:00Z", datetime(2026, 9, 1, 12, 30, tzinfo=UTC)),
        ("2026-09-01T12:30:00.123456Z", datetime(2026, 9, 1, 12, 30, 0, 123456, UTC)),
        ("2026-09-01T14:30:00+02:00", datetime(2026, 9, 1, 12, 30, tzinfo=UTC)),
        ("2026-09-01", datetime(2026, 9, 1)),
    ],
)
def test_single_datetime_sets_both_temporal_bounds(value, expected):
    """An instantaneous observation has equal start and end bounds."""
    umm = {"GranuleUR": "snapshot", "TemporalExtent": {"SingleDateTime": value}}
    original = deepcopy(umm)
    assert extract_granule_temporal_extent(umm) == (expected, expected)
    normalized = normalize_granule_item({"meta": {"concept-id": "G123-PROV"}, "umm": umm})
    assert normalized["time_start"] == expected
    assert normalized["time_end"] == expected
    assert normalized["granule_ur"] == "snapshot"
    assert umm == original


@pytest.mark.parametrize("value", ["", "not-a-date", None, 42, [], {}])
def test_unusable_single_times_remain_absent(value):
    """Missing or malformed metadata must not invent an observation time."""
    assert extract_granule_temporal_extent({"TemporalExtent": {"SingleDateTime": value}}) == (
        None,
        None,
    )


@pytest.mark.parametrize("extent", [None, "unknown", [], {}])
def test_missing_extent_is_unchanged(extent):
    """Retain the existing handling of an absent or non-object temporal extent."""
    assert extract_granule_temporal_extent({"TemporalExtent": extent}) == (None, None)


def test_existing_range_precedence_and_open_end_are_unchanged():
    """A recognized range still takes precedence in mixed nonconforming input."""
    start = datetime(2026, 9, 1, tzinfo=UTC)
    extent = {
        "RangeDateTime": {"BeginningDateTime": "2026-09-01T00:00:00Z"},
        "SingleDateTime": "2026-09-02T00:00:00Z",
    }
    assert extract_granule_temporal_extent({"TemporalExtent": extent}) == (start, None)


def test_multiple_ranges_still_use_outer_bounds():
    """Preserve the existing alternate range-list support."""
    extent = {
        "RangeDateTimes": [
            {"BeginningDateTime": "2026-09-03T00:00:00Z", "EndingDateTime": "2026-09-04T00:00:00Z"},
            {"BeginningDateTime": "2026-09-01T00:00:00Z", "EndingDateTime": "2026-09-02T00:00:00Z"},
        ]
    }
    assert extract_granule_temporal_extent({"TemporalExtent": extent}) == (
        datetime(2026, 9, 1, tzinfo=UTC),
        datetime(2026, 9, 4, tzinfo=UTC),
    )


@pytest.mark.parametrize("fields", [None, ["time_start", "time_end"]])
def test_get_granules_preserves_single_datetime_through_response_model(mock_all_requests, fields):
    """Use the actual tool, HTTP client, normalizer and output model."""
    from tools.get_granules.tool import get_granules

    mock_all_requests.add(
        responses.GET,
        f"{CMR_URL}/search/granules.umm_json",
        json={
            "items": [
                {
                    "meta": {"concept-id": "G123-PROV", "parent-collection-id": "C123-PROV"},
                    "umm": {
                        "GranuleUR": "instantaneous-scene",
                        "TemporalExtent": {"SingleDateTime": "2026-09-01T12:30:00.125Z"},
                    },
                }
            ]
        },
        headers={"CMR-Hits": "1", "CMR-Took": "3"},
    )
    output = get_granules(collection_concept_id="C123-PROV", fields=fields)
    expected = datetime(2026, 9, 1, 12, 30, 0, 125000, UTC)
    assert output["status"] == "success"
    assert output["total_hits"] == 1
    assert output["next_cursor"] is None
    assert output["granules"][0]["concept_id"] == "G123-PROV"
    assert output["granules"][0]["granule_ur"] == "instantaneous-scene"
    assert output["granules"][0]["time_start"] == expected
    assert output["granules"][0]["time_end"] == expected
    assert len(mock_all_requests.calls) == 1
