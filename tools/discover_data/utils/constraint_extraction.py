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
    explicit_temporal: TemporalConstraint | None = None,
    explicit_spatial: SpatialConstraint | None = None,
) -> tuple[TemporalConstraint, SpatialConstraint]:
    """
    Extract temporal and spatial constraints from a query.

    Uses explicit constraints if provided, otherwise extracts from the query.

    Args:
        query: Natural language query
        explicit_temporal: User-provided temporal constraint (skips extraction if provided)
        explicit_spatial: User-provided spatial constraint (skips extraction if provided)

    Returns:
        Tuple of (TemporalConstraint, SpatialConstraint)
    """
    trimmed_query = query.strip()

    if explicit_temporal is not None:
        temporal = explicit_temporal
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

    if explicit_spatial is not None:
        spatial = explicit_spatial
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
