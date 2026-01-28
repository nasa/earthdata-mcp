"""Tests for discover_data orchestrator tool."""

import importlib
import sys
from types import ModuleType
from unittest.mock import MagicMock

from tools.discover_data.input_model import (
    DiscoverDataInput,
    SearchContext,
    SpatialConstraint,
    TemporalConstraint,
)
from tools.discover_data.output_model import ClarifyingQuestion, CollectionMatch, ResolutionInfo


def _make_collection(
    concept_id: str, match_type: str = "direct", metadata: dict | None = None
) -> CollectionMatch:
    return CollectionMatch(
        concept_id=concept_id,
        title=f"Title {concept_id}",
        abstract=None,
        similarity_score=0.9,
        match_type=match_type,
        matched_attribute="title",
        resolution=ResolutionInfo(),
        temporal_coverage=None,
        platforms=[],
        instruments=[],
        related_entity_id=None,
        related_entity_text=None,
        # attach metadata for temporal disambiguation path
        **({"metadata": metadata} if metadata is not None else {}),
    )


def _make_collection_dict(
    concept_id: str, match_type: str = "direct", metadata: dict | None = None
) -> dict:
    """Create a dict result like score_and_rank_collections returns.

    This should match the structure of embedding results with:
    - external_id: CMR concept ID
    - text_content: Matched text (title)
    - attribute: Which attribute matched
    - similarity: Semantic similarity score
    - match_type: How collection was found
    """
    result = {
        "type": "collection",
        "external_id": concept_id,
        "text_content": f"Title {concept_id}",
        "attribute": "title",
        "score": 0.9,
        "match_type": match_type,
        "similarity": 0.9,
    }
    if metadata is not None:
        result["metadata"] = metadata
    return result


def _load_tool():
    """Load tool module with stubbed dependencies to avoid import errors."""
    # Stub util.enrichment before importing tool
    if "util.enrichment" not in sys.modules:
        mod = ModuleType("util.enrichment")
        mod.enrich_metadata = lambda *a, **k: []
        mod.filter_by_spatial_constraint = lambda cols, *a, **k: cols
        mod.filter_by_temporal_constraint = lambda cols, *a, **k: cols
        sys.modules["util.enrichment"] = mod

    return importlib.import_module("tools.discover_data.tool")


def test_extract_or_use_constraints_prefers_previous_context():
    """Test that previous context constraints are preferred over extracting new ones."""
    tool = _load_tool()
    prior_temporal = TemporalConstraint(reasoning="prev")
    prior_spatial = SpatialConstraint(reasoning="prev")
    prev_ctx = SearchContext(temporal=prior_temporal, spatial=prior_spatial)
    query = DiscoverDataInput(query="q", previous_context=prev_ctx)

    temporal, spatial = tool._extract_or_use_constraints(query)

    assert temporal is prior_temporal
    assert spatial is prior_spatial


def test_discover_data_expansion_path(monkeypatch):
    """Test that query expansion path suggests refinement questions."""
    tool = _load_tool()

    temporal = TemporalConstraint()
    spatial = SpatialConstraint()

    monkeypatch.setattr(
        tool,
        "extract_constraints",
        lambda q, explicit_temporal, explicit_spatial: (temporal, spatial),
    )
    monkeypatch.setattr(
        tool,
        "search_all_entity_types",
        lambda *_args, **_kwargs: [{"type": "variable", "similarity": 0.6}],
    )
    monkeypatch.setattr(
        tool, "score_and_rank_collections", lambda *_args, **_kwargs: [_make_collection_dict("C1")]
    )
    monkeypatch.setattr(
        tool, "hydrate_collections", lambda *_args, **_kwargs: [_make_collection("C1")]
    )
    monkeypatch.setattr(tool, "should_expand_query", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(tool, "_describe_search_strategy", lambda *a, **k: "desc")

    ctx_obj = object()
    monkeypatch.setattr(tool, "analyze_embedding_results", lambda results: ctx_obj)
    questions = [ClarifyingQuestion(question_id="q1"), ClarifyingQuestion(question_id="q2")]
    monkeypatch.setattr(tool, "generate_expansion_questions", lambda query_text, context: questions)

    query = DiscoverDataInput(query="ocean color")

    output = tool.discover_data(query)

    assert output["status"] == "refinement_suggested"
    assert [q["question_id"] for q in output["clarifying_questions"]] == ["q1", "q2"]
    assert output["collections"]


def test_discover_data_disambiguation_path(monkeypatch):
    """Test that disambiguation path presents clarifying questions."""
    tool = _load_tool()

    temporal = TemporalConstraint()
    spatial = SpatialConstraint()
    monkeypatch.setattr(tool, "extract_constraints", lambda *_args, **_kwargs: (temporal, spatial))
    monkeypatch.setattr(
        tool,
        "search_all_entity_types",
        lambda *_args, **_kwargs: [
            {"type": "collection", "similarity": 0.8, "match_type": "direct"}
        ],
    )

    # Return two collections so filtered_collections not empty
    collections_dict = [
        _make_collection_dict("C1", metadata={"TemporalExtents": []}),
        _make_collection_dict("C2", metadata={"TemporalExtents": []}),
    ]
    collections_match = [
        _make_collection("C1"),
        _make_collection("C2"),
    ]
    monkeypatch.setattr(
        tool, "score_and_rank_collections", lambda *_args, **_kwargs: collections_dict
    )
    monkeypatch.setattr(tool, "hydrate_collections", lambda *_args, **_kwargs: collections_match)
    monkeypatch.setattr(tool, "_describe_search_strategy", lambda *a, **k: "desc")

    # Ensure user refinements are applied
    applied = {}

    def fake_filter_by_user_refinements(cols, refinements):
        applied.update(refinements)
        return cols

    monkeypatch.setattr(tool, "filter_by_user_refinements", fake_filter_by_user_refinements)

    prev_ctx = SearchContext(temporal=None, spatial=None, user_refinements={"a": "b"})
    query = DiscoverDataInput(query="snow", previous_context=prev_ctx)

    output = tool.discover_data(query)

    assert output["status"] == "collections_found"
    assert applied == {"a": "b"}
    assert output["clarifying_questions"] == []
    assert len(output["collections"]) == 2


def test_determine_status_variants():
    """Test that discovery status is determined correctly for different result scenarios."""
    tool = importlib.import_module("tools.discover_data.tool")
    direct = _make_collection("C1", match_type="direct")
    indirect = _make_collection("C2", match_type="via_variable")

    assert tool._determine_status([], [], []) == tool.DiscoveryStatus.NO_RESULTS
    assert tool._determine_status([direct], True, []) == tool.DiscoveryStatus.DISAMBIGUATION_NEEDED
    assert tool._determine_status([indirect], False, []) == tool.DiscoveryStatus.INDIRECT_MATCHES
    assert (
        tool._determine_status([direct], False, [{"match_type": "direct"}])
        == tool.DiscoveryStatus.COLLECTIONS_FOUND
    )


def test_describe_search_strategy_counts():
    """Test that search strategy description includes correct match type counts."""
    tool = importlib.import_module("tools.discover_data.tool")
    temporal = TemporalConstraint(start_date=None, end_date=None)
    spatial = SpatialConstraint(wkt_geometry="POLYGON(...)")
    ranked = [
        {"match_type": "direct"},
        {"match_type": "direct_and_indirect"},
        {"match_type": "via_variable"},
    ]

    desc = tool._describe_search_strategy(temporal, spatial, ranked)

    assert "direct collection matches" in desc
    assert "collections found via related entities" in desc
    assert "spatial filtering" in desc


def test_discover_data_error_handling(monkeypatch):
    """Discover data should catch exceptions and return error status."""
    tool = _load_tool()

    # Create a mock that raises an exception
    def raise_error(*args, **kwargs):
        raise RuntimeError("Extraction failed")

    monkeypatch.setattr(tool, "extract_constraints", raise_error)
    query = DiscoverDataInput(query="test")

    output = tool.discover_data(query)

    assert output["status"] == "error"
    assert "Extraction failed" in output["error_message"]


def test_discover_data_with_langfuse(monkeypatch):
    """Discover data should log to Langfuse when available."""
    import util.langfuse

    tool = _load_tool()

    # Create a mock Langfuse client
    mock_langfuse = MagicMock()
    monkeypatch.setattr(util.langfuse, "get_langfuse", lambda: mock_langfuse)

    temporal = TemporalConstraint()
    spatial = SpatialConstraint()

    monkeypatch.setattr(
        tool,
        "extract_constraints",
        lambda q, explicit_temporal, explicit_spatial: (temporal, spatial),
    )
    monkeypatch.setattr(
        tool,
        "search_all_entity_types",
        lambda *_args, **_kwargs: [
            {"type": "collection", "similarity": 0.8, "match_type": "direct"}
        ],
    )
    monkeypatch.setattr(
        tool, "score_and_rank_collections", lambda *_args, **_kwargs: [_make_collection_dict("C1")]
    )
    monkeypatch.setattr(
        tool, "hydrate_collections", lambda *_args, **_kwargs: [_make_collection("C1")]
    )
    monkeypatch.setattr(tool, "should_expand_query", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(tool, "filter_by_user_refinements", lambda cols, refs: cols)
    monkeypatch.setattr(tool, "_describe_search_strategy", lambda *a, **k: "desc")

    query = DiscoverDataInput(query="test collection")
    output = tool.discover_data(query)

    # Verify Langfuse methods were called
    assert mock_langfuse.update_current_trace.called
    assert output["status"] == "collections_found"
