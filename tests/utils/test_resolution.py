"""Tests for util.resolution."""

from typing import Any

from util.resolution import Resolution, check_disambiguation, group_by_resolution


class MockResolution:
    """Mock resolution."""

    def __init__(self, unit: str, val: str):
        self.unit = unit
        self.val = val

    def __str__(self) -> str:
        return self.val


def test_group_by_resolution():
    """Test function."""
    c1 = {"id": 1}
    c2 = {"id": 2}
    c3 = {"id": 3}

    def extract(c: dict[str, Any]) -> Resolution | None:
        if c["id"] == 1 or c["id"] == 2:
            return MockResolution("meters", "10 meters")
        return None

    res = group_by_resolution([c1, c2, c3], extract)
    assert res["10 meters"] == [c1, c2]
    assert res[None] == [c3]


def test_check_disambiguation():
    """Test function."""
    c1 = {"id": 1}
    c2 = {"id": 2}
    c3 = {"id": 3}
    c4 = {"id": 4}

    def extract(c: dict[str, Any]) -> Resolution | None:
        if c["id"] == 1:
            return MockResolution("meters", "10")
        if c["id"] == 2:
            return MockResolution("meters", "20")
        if c["id"] == 3:
            return MockResolution("Varies", "Varies")
        return None

    def sort_key(s: str) -> float:
        return float(s)

    needs, diffs = check_disambiguation(
        [c1, c2, c3, c4], extract, exclude_units=("Varies",), sort_key_fn=sort_key
    )

    assert needs is True
    assert diffs == ["10", "20"]


def test_check_disambiguation_no_need():
    """Test function."""
    c1 = {"id": 1}
    c2 = {"id": 2}

    def extract(c: dict[str, Any]) -> Resolution | None:
        if c["id"] == 1 or c["id"] == 2:
            return MockResolution("meters", "10")
        return None

    needs, diffs = check_disambiguation(
        [c1, c2], extract, exclude_units=("Varies",), sort_key_fn=float
    )

    assert needs is False
    assert diffs == ["10"]
