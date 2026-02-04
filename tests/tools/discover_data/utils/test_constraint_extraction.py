"""Tests for constraint_extraction utility module."""

from datetime import UTC, datetime

from tools.discover_data.utils import constraint_extraction
from tools.models.constraints import SpatialConstraint, TemporalConstraint


def test_extract_constraints_extracts_both_when_no_explicit(monkeypatch):
    """Without explicit constraints, should call extraction functions."""
    temporal_result = TemporalConstraint(start_date=datetime(2020, 1, 1, tzinfo=UTC), end_date=None)
    spatial_result = SpatialConstraint(location="Denver", wkt_geometry="...")

    def fake_temporal(_query):
        return temporal_result

    def fake_spatial(_query):
        return spatial_result

    monkeypatch.setattr(constraint_extraction, "extract_temporal_constraint", fake_temporal)
    monkeypatch.setattr(constraint_extraction, "extract_spatial_constraint", fake_spatial)

    temporal, spatial = constraint_extraction.extract_constraints("data from 2020 in Denver")

    assert temporal == temporal_result
    assert spatial == spatial_result


def test_extract_constraints_handles_temporal_extraction_error(monkeypatch):
    """If temporal extraction fails, should return neutral constraint."""
    spatial_result = SpatialConstraint(location="Denver")

    def fake_temporal(_query):
        raise ValueError("LLM failed")

    def fake_spatial(_query):
        return spatial_result

    monkeypatch.setattr(constraint_extraction, "extract_temporal_constraint", fake_temporal)
    monkeypatch.setattr(constraint_extraction, "extract_spatial_constraint", fake_spatial)

    temporal, spatial = constraint_extraction.extract_constraints("query")

    assert temporal.start_date is None
    assert temporal.end_date is None
    assert "Extraction failed" in temporal.reasoning
    assert spatial == spatial_result


def test_extract_constraints_handles_spatial_extraction_error(monkeypatch):
    """If spatial extraction fails, should return neutral constraint."""
    temporal_result = TemporalConstraint(start_date=datetime(2020, 1, 1, tzinfo=UTC))

    def fake_temporal(_query):
        return temporal_result

    def fake_spatial(_query):
        raise RuntimeError("Geocoding failed")

    monkeypatch.setattr(constraint_extraction, "extract_temporal_constraint", fake_temporal)
    monkeypatch.setattr(constraint_extraction, "extract_spatial_constraint", fake_spatial)

    temporal, spatial = constraint_extraction.extract_constraints("query")

    assert temporal == temporal_result
    assert spatial.location is None
    assert spatial.wkt_geometry is None
    assert "Extraction failed" in spatial.reasoning


def test_extract_constraints_uses_explicit_temporal_if_provided(monkeypatch):
    """If prior temporal is provided, should not call extraction."""
    prior_temporal = TemporalConstraint(start_date=datetime(2015, 1, 1, tzinfo=UTC))
    spatial_result = SpatialConstraint(location="Denver")

    temporal_calls = []
    spatial_calls = []

    def fake_temporal(query):
        temporal_calls.append(query)
        return TemporalConstraint()

    def fake_spatial(query):
        spatial_calls.append(query)
        return spatial_result

    monkeypatch.setattr(constraint_extraction, "extract_temporal_constraint", fake_temporal)
    monkeypatch.setattr(constraint_extraction, "extract_spatial_constraint", fake_spatial)

    temporal, _ = constraint_extraction.extract_constraints(
        "data from 2020 in Denver",
        prior_temporal=prior_temporal,
    )

    assert temporal == prior_temporal
    assert not temporal_calls  # Should not have called extraction
    assert spatial_calls == ["data from 2020 in Denver"]


def test_extract_constraints_uses_explicit_spatial_if_provided(monkeypatch):
    """If prior spatial is provided, should not call extraction."""
    temporal_result = TemporalConstraint(start_date=datetime(2020, 1, 1, tzinfo=UTC))
    prior_spatial = SpatialConstraint(location="Los Angeles")

    temporal_calls = []
    spatial_calls = []

    def fake_temporal(query):
        temporal_calls.append(query)
        return temporal_result

    def fake_spatial(query):
        spatial_calls.append(query)
        return SpatialConstraint()

    monkeypatch.setattr(constraint_extraction, "extract_temporal_constraint", fake_temporal)
    monkeypatch.setattr(constraint_extraction, "extract_spatial_constraint", fake_spatial)

    _, spatial = constraint_extraction.extract_constraints(
        "data from 2020 in Denver",
        prior_spatial=prior_spatial,
    )

    assert spatial == prior_spatial
    assert not spatial_calls  # Should not have called extraction
    assert temporal_calls == ["data from 2020 in Denver"]


def test_extract_constraints_uses_both_explicit_if_provided(monkeypatch):
    """If both prior constraints are provided, should not call any extraction."""
    prior_temporal = TemporalConstraint(start_date=datetime(2015, 1, 1, tzinfo=UTC))
    prior_spatial = SpatialConstraint(location="Los Angeles")

    temporal_calls = []
    spatial_calls = []

    def fake_temporal(query):
        temporal_calls.append(query)
        return TemporalConstraint()

    def fake_spatial(query):
        spatial_calls.append(query)
        return SpatialConstraint()

    monkeypatch.setattr(constraint_extraction, "extract_temporal_constraint", fake_temporal)
    monkeypatch.setattr(constraint_extraction, "extract_spatial_constraint", fake_spatial)

    temporal, spatial = constraint_extraction.extract_constraints(
        "some query",
        prior_temporal=prior_temporal,
        prior_spatial=prior_spatial,
    )

    assert temporal == prior_temporal
    assert spatial == prior_spatial
    assert not temporal_calls
    assert not spatial_calls
