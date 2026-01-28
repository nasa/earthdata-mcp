"""
Constraint extraction utilities for discover_data orchestrator.

Wraps temporal and spatial extraction utilities to produce TemporalConstraint
and SpatialConstraint objects from natural language queries.

These wrappers handle:
- Empty/None query guards
- Error handling and graceful degradation
- Structured output (Pydantic models with reasoning)

Individual extraction logic lives in extract_temporal_constraint.py and
extract_spatial_constraint.py for testability and reusability.
"""

import logging

from tools.discover_data.input_model import SpatialConstraint, TemporalConstraint

from .extract_spatial_constraint import extract_spatial_constraint
from .extract_temporal_constraint import extract_temporal_constraint

logger = logging.getLogger(__name__)


def extract_temporal_constraint_from_query(query: str) -> TemporalConstraint:
    """
    Extract temporal constraints from a natural language query.

    Uses the temporal range extraction utility to parse dates.

    Args:
        query: Natural language query that may contain temporal references

    Returns:
        TemporalConstraint with extracted start/end dates and reasoning
    """
    try:
        return extract_temporal_constraint(query)
    except Exception as e:
        logger.warning("Failed to extract temporal constraint: %s", e)
        return TemporalConstraint(
            start_date=None,
            end_date=None,
            reasoning=f"Extraction failed: {e}",
        )


def extract_spatial_constraint_from_query(query: str) -> SpatialConstraint:
    """
    Extract spatial constraints from a natural language query.

    Uses LLM-based extraction to identify spatial information,
    then geocodes the location and returns WKT geometry.

    Args:
        query: Natural language query that may contain location references

    Returns:
        SpatialConstraint with location text and WKT geometry
    """
    try:
        return extract_spatial_constraint(query)
    except Exception as e:
        logger.warning("Failed to extract spatial constraint: %s", e)
        return SpatialConstraint(
            location=None,
            wkt_geometry=None,
            reasoning=f"Extraction failed: {e}",
        )


def extract_constraints(
    query: str,
    explicit_temporal: TemporalConstraint | None = None,
    explicit_spatial: SpatialConstraint | None = None,
) -> tuple[TemporalConstraint, SpatialConstraint]:
    """
    Extract both temporal and spatial constraints from a query.

    Uses explicit constraints if provided, otherwise extracts from the query.

    Args:
        query: Natural language query
        explicit_temporal: User-provided temporal constraint (skips extraction if provided)
        explicit_spatial: User-provided spatial constraint (skips extraction if provided)

    Returns:
        Tuple of (TemporalConstraint, SpatialConstraint)
    """
    temporal = (
        explicit_temporal
        if explicit_temporal is not None
        else extract_temporal_constraint_from_query(query)
    )

    spatial = (
        explicit_spatial
        if explicit_spatial is not None
        else extract_spatial_constraint_from_query(query)
    )

    return temporal, spatial
