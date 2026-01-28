"""
LLM-specific data models for discover_data tool.

For shared models (constraints, input, output), import from tools.models:
  from tools.models.constraints import TemporalConstraint, SpatialConstraint
  from tools.models.input_model import DiscoverDataInput, SearchContext
  from tools.models.output_model import CollectionMatch, DiscoverDataOutput

For discover-data-specific LLM extraction models, import from here:
  from tools.discover_data.models.llm import SpatialExtractionResult, TemporalRangeOutput
"""

from tools.discover_data.models.llm import (
    SpatialExtractionOutput,
    SpatialExtractionResult,
    TemporalRangeOutput,
)

__all__ = [
    # LLM models
    "TemporalRangeOutput",
    "SpatialExtractionOutput",
    "SpatialExtractionResult",
]
