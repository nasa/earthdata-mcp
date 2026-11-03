"""Tests for MapSpec and validate_bounds."""

import pytest
from pydantic import ValidationError

from util.visualization.specs import MapSpec, validate_bounds


def test_validate_bounds_ok():
    """Valid bounds should be returned as a list of floats."""
    assert validate_bounds([-74, 40, -73, 41]) == [-74.0, 40.0, -73.0, 41.0]


def test_validate_bounds_south_gt_north():
    """south > north should raise ValueError."""
    with pytest.raises(ValueError, match="south > north"):
        validate_bounds([0, 50, 1, 10])


def test_validate_bounds_lon_out_of_range():
    """Longitude outside [-180, 180] should raise ValueError."""
    with pytest.raises(ValueError, match="longitude"):
        validate_bounds([-200, 0, 0, 10])


def test_map_spec_minimal():
    """Minimal MapSpec should have None collection_id, bounds, and initial_bounds."""
    spec = MapSpec(title="Test")
    assert spec.collection_id is None
    assert spec.bounds is None
    assert spec.initial_bounds() is None


def test_map_spec_with_collection_id():
    """collection_id should be stored and retrievable."""
    spec = MapSpec(title="Test", collection_id="C1276812859-GES_DISC")
    assert spec.collection_id == "C1276812859-GES_DISC"


def test_map_spec_explicit_bounds_validated():
    """MapSpec should reject bounds where south > north at construction time."""
    with pytest.raises(ValidationError, match="south > north"):
        MapSpec(title="t", bounds=[0, 50, 1, 10])


def test_map_spec_initial_bounds():
    """initial_bounds should return the [W, S, E, N] list when bounds are set."""
    spec = MapSpec(title="t", bounds=[-10, 0, 10, 20])
    assert spec.initial_bounds() == [-10.0, 0.0, 10.0, 20.0]
