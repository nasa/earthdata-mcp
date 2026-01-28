"""
Shared data models for tools.

This package exports common models used across multiple tools:
- Constraints: TemporalConstraint, SpatialConstraint (spatial/temporal filtering)
- Input models: DiscoverDataInput, SearchContext (tool input schemas)
- Output models: DiscoverDataOutput, CollectionMatch, etc. (tool results)

Direct submodule imports are recommended for clarity:
  from tools.models.constraints import TemporalConstraint, SpatialConstraint
  from tools.models.input_model import DiscoverDataInput
  from tools.models.output_model import CollectionMatch, DiscoverDataOutput
"""

from tools.models.constraints import SpatialConstraint, TemporalConstraint
from tools.models.input_model import DiscoverDataInput, SearchContext
from tools.models.output_model import (
    ClarifyingQuestion,
    CollectionMatch,
    DiscoverDataOutput,
    DiscoveryStatus,
    ExtractedConstraints,
    ResolutionInfo,
    TemporalCoverage,
)

__all__ = [
    # Constraint models
    "TemporalConstraint",
    "SpatialConstraint",
    # Input models
    "DiscoverDataInput",
    "SearchContext",
    # Output models
    "DiscoverDataOutput",
    "DiscoveryStatus",
    "CollectionMatch",
    "ResolutionInfo",
    "TemporalCoverage",
    "ClarifyingQuestion",
    "ExtractedConstraints",
]
