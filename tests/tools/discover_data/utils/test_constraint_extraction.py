"""Tests for constraint_extraction utility module."""

from datetime import UTC, datetime

import pytest

from tools.discover_data.input_model import SpatialConstraint, TemporalConstraint
from tools.discover_data.utils import constraint_extraction


def test_extract_temporal_constraint_from_query_success(monkeypatch):
    """Temporal wrapper should pass through successful extraction."""
    expected = TemporalConstraint(
        start_date=datetime(2020, 1, 1, tzinfo=UTC),
        end_date=datetime(2020, 12, 31, tzinfo=UTC),
        reasoning="Parsed as calendar year 2020",
    )

    def fake_extract(_query):
        return expected

    monkeypatch.setattr(constraint_extraction, "extract_temporal_constraint", fake_extract)

    result = constraint_extraction.extract_temporal_constraint_from_query("data from 2020")

    assert result == expected


def test_extract_temporal_constraint_from_query_error_handling(monkeypatch):
    """Temporal wrapper should catch exceptions and return neutral constraint."""

    def fake_extract(_query):
        raise ValueError("LLM failed")

    monkeypatch.setattr(constraint_extraction, "extract_temporal_constraint", fake_extract)

    result = constraint_extraction.extract_temporal_constraint_from_query("malformed query")

    assert result.start_date is None
    assert result.end_date is None
    assert "Extraction failed" in result.reasoning


def test_extract_spatial_constraint_from_query_success(monkeypatch):
    """Spatial wrapper should pass through successful extraction."""
    expected = SpatialConstraint(
        location="Colorado",
        wkt_geometry="POLYGON(...)",
        reasoning="Geocoded to state boundary",
    )

    def fake_extract(_query):
        return expected

    monkeypatch.setattr(constraint_extraction, "extract_spatial_constraint", fake_extract)

    result = constraint_extraction.extract_spatial_constraint_from_query("data for Colorado")

    assert result == expected


def test_extract_spatial_constraint_from_query_error_handling(monkeypatch):
    """Spatial wrapper should catch exceptions and return neutral constraint."""

    def fake_extract(_query):
        raise RuntimeError("Geocoding failed")

    monkeypatch.setattr(constraint_extraction, "extract_spatial_constraint", fake_extract)

    result = constraint_extraction.extract_spatial_constraint_from_query("invalid location")

    assert result.location is None
    assert result.wkt_geometry is None
    assert "Extraction failed" in result.reasoning


def test_extract_constraints_uses_wrappers_when_no_explicit(monkeypatch):
    """Without explicit constraints, should call the wrappers."""
    temporal_result = TemporalConstraint(start_date=datetime(2020, 1, 1, tzinfo=UTC), end_date=None)
    spatial_result = SpatialConstraint(location="Denver", wkt_geometry="...")

    def fake_temporal(_query):
        return temporal_result

    def fake_spatial(_query):
        return spatial_result

    monkeypatch.setattr(constraint_extraction, "extract_temporal_constraint_from_query", fake_temporal)
    monkeypatch.setattr(constraint_extraction, "extract_spatial_constraint_from_query", fake_spatial)

    temporal, spatial = constraint_extraction.extract_constraints("data from 2020 in Denver")

    assert temporal == temporal_result
    assert spatial == spatial_result


def test_extract_constraints_uses_explicit_temporal_if_provided(monkeypatch):
    """If explicit temporal is provided, should not call the wrapper."""
    explicit_temporal = TemporalConstraint(start_date=datetime(2015, 1, 1, tzinfo=UTC))
    spatial_result = SpatialConstraint(location_query="Denver")

    temporal_calls = []
    spatial_calls = []

    def fake_temporal(query):
        temporal_calls.append(query)
        return TemporalConstraint()

    def fake_spatial(query):
        spatial_calls.append(query)
        return spatial_result

    monkeypatch.setattr(constraint_extraction, "extract_temporal_constraint_from_query", fake_temporal)
    monkeypatch.setattr(constraint_extraction, "extract_spatial_constraint_from_query", fake_spatial)

    temporal, spatial = constraint_extraction.extract_constraints(
        "data from 2020 in Denver",
        explicit_temporal=explicit_temporal,
    )

    assert temporal == explicit_temporal
    assert temporal_calls == []  # Should not have called the wrapper
    assert spatial_calls == ["data from 2020 in Denver"]


def test_extract_constraints_uses_explicit_spatial_if_provided(monkeypatch):
    """If explicit spatial is provided, should not call the wrapper."""
    temporal_result = TemporalConstraint(start_date=datetime(2020, 1, 1, tzinfo=UTC))
    explicit_spatial = SpatialConstraint(location="Los Angeles")

    temporal_calls = []
    spatial_calls = []

    def fake_temporal(query):
        temporal_calls.append(query)
        return temporal_result

    def fake_spatial(query):
        spatial_calls.append(query)
        return SpatialConstraint()

    monkeypatch.setattr(constraint_extraction, "extract_temporal_constraint_from_query", fake_temporal)
    monkeypatch.setattr(constraint_extraction, "extract_spatial_constraint_from_query", fake_spatial)

    temporal, spatial = constraint_extraction.extract_constraints(
        "data from 2020 in Denver",
        explicit_spatial=explicit_spatial,
    )

    assert spatial == explicit_spatial
    assert spatial_calls == []  # Should not have called the wrapper
    assert temporal_calls == ["data from 2020 in Denver"]


def test_extract_constraints_uses_both_explicit_if_provided(monkeypatch):
    """If both explicit constraints are provided, should not call any wrappers."""
    explicit_temporal = TemporalConstraint(start_date=datetime(2015, 1, 1, tzinfo=UTC))
    explicit_spatial = SpatialConstraint(location="Los Angeles")

    temporal_calls = []
    spatial_calls = []

    def fake_temporal(query):
        temporal_calls.append(query)
        return TemporalConstraint()

    def fake_spatial(query):
        spatial_calls.append(query)
        return SpatialConstraint()

    monkeypatch.setattr(constraint_extraction, "extract_temporal_constraint_from_query", fake_temporal)
    monkeypatch.setattr(constraint_extraction, "extract_spatial_constraint_from_query", fake_spatial)

    temporal, spatial = constraint_extraction.extract_constraints(
        "some query",
        explicit_temporal=explicit_temporal,
        explicit_spatial=explicit_spatial,
    )

    assert temporal == explicit_temporal
    assert spatial == explicit_spatial
    assert temporal_calls == []
    assert spatial_calls == []
