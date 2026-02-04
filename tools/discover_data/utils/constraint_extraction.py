"""
Constraint extraction for discover_data orchestrator.
"""

import logging

from tools.models.constraints import SpatialConstraint, TemporalConstraint

from .extract_spatial_constraint import extract_spatial_constraint
from .extract_temporal_constraint import extract_temporal_constraint

logger = logging.getLogger(__name__)


def extract_constraints(
    query: str,
    prior_temporal: TemporalConstraint | None = None,
    prior_spatial: SpatialConstraint | None = None,
) -> tuple[TemporalConstraint, SpatialConstraint]:
    """
    Extract temporal and spatial constraints from a query.

    Uses prior constraints from search context if provided, otherwise extracts from the query.
    If the user changes a constraint, callers must pass None for that parameter to trigger
    re-extraction from the query.

    Args:
        query: Natural language query
        prior_temporal: Temporal constraint from previous search iteration (skips extraction if provided).
                       Pass None to force re-extraction when user changes temporal constraints.
        prior_spatial: Spatial constraint from previous search iteration (skips extraction if provided).
                      Pass None to force re-extraction when user changes spatial constraints.

    Returns:
        Tuple of (TemporalConstraint, SpatialConstraint)
    """
    trimmed_query = query.strip()

    if prior_temporal is not None:
        temporal = prior_temporal
    else:
        try:
            temporal = extract_temporal_constraint(trimmed_query)
        except Exception as e:
            logger.warning("Failed to extract temporal constraint: %s", e)
            temporal = TemporalConstraint(
                start_date=None,
                end_date=None,
                reasoning=f"Extraction failed: {e}",
            )

    if prior_spatial is not None:
        spatial = prior_spatial
    else:
        try:
            spatial = extract_spatial_constraint(trimmed_query)
        except Exception as e:
            logger.warning("Failed to extract spatial constraint: %s", e)
            spatial = SpatialConstraint(
                location=None,
                wkt_geometry=None,
                reasoning=f"Extraction failed: {e}",
            )

    return temporal, spatial
