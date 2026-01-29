"""Tests for discover_data orchestrator tool."""

import importlib
import sys
from types import ModuleType
from unittest.mock import MagicMock

from tools.models.constraints import SpatialConstraint, TemporalConstraint
from tools.models.input_model import DiscoverDataInput, SearchContext
from tools.models.output_model import (
    ClarifyingQuestion,
    CollectionMatch,
    ResolutionInfo,
)


def _make_collection(concept_id: str, match_type: str = "direct") -> CollectionMatch:
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


def test_extract_or_use_constraints_prefers_previous_context_when_no_explicit():
    """Test that previous context constraints are used when no explicit ones are provided."""
    tool = _load_tool()
    prior_temporal = TemporalConstraint(reasoning="prev")
    prior_spatial = SpatialConstraint(reasoning="prev")
    prev_ctx = SearchContext(temporal=prior_temporal, spatial=prior_spatial)
    query = DiscoverDataInput(query="q", previous_context=prev_ctx)

    temporal, spatial = tool._extract_or_use_constraints(query)

    assert temporal is prior_temporal
    assert spatial is prior_spatial


def test_extract_or_use_constraints_prefers_explicit_over_previous_context():
    """Test that explicit constraints override previous context constraints."""
    tool = _load_tool()
    prior_temporal = TemporalConstraint(reasoning="prev")
    prior_spatial = SpatialConstraint(reasoning="prev")
    explicit_temporal = TemporalConstraint(reasoning="explicit")
    explicit_spatial = SpatialConstraint(reasoning="explicit")
    prev_ctx = SearchContext(temporal=prior_temporal, spatial=prior_spatial)
    query = DiscoverDataInput(
        query="q",
        previous_context=prev_ctx,
        temporal_constraint=explicit_temporal,
        spatial_constraint=explicit_spatial,
    )

    temporal, spatial = tool._extract_or_use_constraints(query)

    assert temporal is explicit_temporal
    assert spatial is explicit_spatial


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
    monkeypatch.setattr(tool, "check_disambiguation", lambda cols: (False, []))

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
    monkeypatch.setattr(tool, "should_expand_query", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(tool, "check_disambiguation", lambda cols: (False, []))

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


def test_discover_data_with_disambiguation_questions(monkeypatch):
    """Test that disambiguation returns clarifying questions when needed."""
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
    monkeypatch.setattr(tool, "should_expand_query", lambda *_args, **_kwargs: False)

    # Mock check_disambiguation to return True with clarifying questions
    disamb_questions = [
        ClarifyingQuestion(
            question_id="temporal_res_1",
            question_text="What temporal resolution do you need?",
            question_type="resolution_preference",
            options=["Daily", "Monthly", "Annual"],
            explanations=None,  # No KMS definitions for resolution values
            recommendation=None,
        ),
        ClarifyingQuestion(
            question_id="platform_pref_1",
            question_text="Do you have a preference for satellite platforms?",
            question_type="platform_preference",
            options=["MODIS (Terra/Aqua)", "Landsat", "Sentinel-2"],
            explanations=None,  # Would be populated from KMS definitions in real execution
            recommendation=None,
        ),
    ]
    monkeypatch.setattr(tool, "check_disambiguation", lambda cols: (True, disamb_questions))

    monkeypatch.setattr(tool, "filter_by_user_refinements", lambda cols, refs: cols)

    query = DiscoverDataInput(query="snow")

    output = tool.discover_data(query)

    assert output["status"] == "disambiguation_needed"
    assert [q["question_id"] for q in output["clarifying_questions"]] == [
        "temporal_res_1",
        "platform_pref_1",
    ]
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
    monkeypatch.setattr(tool, "check_disambiguation", lambda cols, *a, **k: (False, []))
    monkeypatch.setattr(tool, "_describe_search_strategy", lambda *a, **k: "desc")

    query = DiscoverDataInput(query="test collection")
    output = tool.discover_data(query)

    # Verify Langfuse methods were called
    assert mock_langfuse.update_current_trace.called
    assert output["status"] == "collections_found"


def test_end_to_end_disambiguation_with_user_refinement(monkeypatch):
    """
    End-to-end test exercising full disambiguation flow with user refinement.
    """
    tool = _load_tool()

    # ========== INITIAL SEARCH PHASE ==========
    temporal = TemporalConstraint(
        start_date=None,
        end_date=None,
        reasoning="No temporal constraint in query",
    )
    spatial = SpatialConstraint(
        location=None,
        wkt_geometry=None,
        reasoning="No spatial constraint in query",
    )

    # Mock constraint extraction to return our known constraints
    monkeypatch.setattr(
        tool,
        "extract_constraints",
        lambda q, explicit_temporal, explicit_spatial: (temporal, spatial),
    )

    # Mock initial embedding search returning multiple entity types
    initial_embedding_results = [
        # Direct collection matches
        {
            "type": "collection",
            "external_id": "G12345_MODIS_1",
            "text_content": "MODIS/Aqua Land Cover Product",
            "attribute": "title",
            "score": 0.92,
            "similarity": 0.92,
            "match_type": "direct",
        },
        {
            "type": "collection",
            "external_id": "G12346_LANDSAT_1",
            "text_content": "Landsat Surface Reflectance",
            "attribute": "title",
            "score": 0.88,
            "similarity": 0.88,
            "match_type": "direct",
        },
        # Indirect matches via instrument
        {
            "type": "instrument",
            "external_id": "I-MODIS",
            "text_content": "Moderate Resolution Imaging Spectroradiometer",
            "attribute": "name",
            "score": 0.85,
            "similarity": 0.85,
        },
        # Indirect matches via variable
        {
            "type": "variable",
            "external_id": "V-NDVI",
            "text_content": "Normalized Difference Vegetation Index",
            "attribute": "name",
            "score": 0.82,
            "similarity": 0.82,
        },
    ]

    monkeypatch.setattr(
        tool,
        "search_all_entity_types",
        lambda *_args, **_kwargs: initial_embedding_results,
    )

    # Mock scoring - maps embeddings to collections with match types
    scored_collections = [
        _make_collection_dict("G12345_MODIS_1", match_type="direct"),
        _make_collection_dict("G12346_LANDSAT_1", match_type="direct"),
        _make_collection_dict("G12345_MODIS_via_instr", match_type="via_instrument"),
    ]

    monkeypatch.setattr(
        tool,
        "score_and_rank_collections",
        lambda *_args, **_kwargs: scored_collections,
    )

    # Mock hydration - returns full collection objects with metadata
    hydrated_collections = [
        CollectionMatch(
            concept_id="G12345_MODIS_1",
            title="MODIS/Aqua Land Cover Product",
            abstract="MODIS land cover classification data",
            similarity_score=0.92,
            match_type="direct",
            matched_attribute="title",
            resolution=ResolutionInfo(
                temporal_resolution="16 Day",
                temporal_resolution_value=16.0,
                spatial_resolution="250m",
                spatial_resolution_value=250.0,
            ),
            temporal_coverage=None,
            platforms=["Aqua"],
            instruments=["MODIS"],
            related_entity_id=None,
            related_entity_text=None,
        ),
        CollectionMatch(
            concept_id="G12346_LANDSAT_1",
            title="Landsat Surface Reflectance",
            abstract="Landsat surface reflectance data",
            similarity_score=0.88,
            match_type="direct",
            matched_attribute="title",
            resolution=ResolutionInfo(
                temporal_resolution="Daily",
                temporal_resolution_value=1.0,
                spatial_resolution="30m",
                spatial_resolution_value=30.0,
            ),
            temporal_coverage=None,
            platforms=["Landsat-8", "Landsat-9"],
            instruments=["OLI"],
            related_entity_id=None,
            related_entity_text=None,
        ),
        CollectionMatch(
            concept_id="G12345_MODIS_via_instr",
            title="MODIS/Terra Land Cover Product",
            abstract="MODIS Terra land cover data",
            similarity_score=0.85,
            match_type="via_instrument",
            matched_attribute="instrument",
            resolution=ResolutionInfo(
                temporal_resolution="8 Day",
                temporal_resolution_value=8.0,
                spatial_resolution="250m",
                spatial_resolution_value=250.0,
            ),
            temporal_coverage=None,
            platforms=["Terra"],
            instruments=["MODIS"],
            related_entity_id="I-MODIS",
            related_entity_text="MODIS Instrument",
        ),
    ]

    monkeypatch.setattr(
        tool,
        "hydrate_collections",
        lambda *_args, **_kwargs: hydrated_collections,
    )

    # Initial search should NOT expand - we have good direct matches
    monkeypatch.setattr(tool, "should_expand_query", lambda *_args, **_kwargs: False)

    # Mock disambiguation to indicate we need to clarify
    # Two candidates with different temporal/spatial resolutions need clarification
    disamb_questions = [
        ClarifyingQuestion(
            question_id="platform_pref_1",
            question_text="Which satellite platform would you prefer?",
            question_type="platform_preference",
            options=["Aqua", "Terra", "Landsat-8", "Landsat-9"],
            explanations={
                "Aqua": "NASA satellite launched in 2002 carrying MODIS and other instruments for studying Earth's water cycle and clouds",
                "Terra": "NASA satellite launched in 1999 carrying MODIS and other instruments for observing Earth's land, atmosphere, and oceans",
                "Landsat-8": "USGS/NASA satellite launched in 2013 providing multispectral imagery with 30m resolution for land surface monitoring",
                "Landsat-9": "USGS/NASA satellite launched in 2021 providing improved multispectral imagery with 30m resolution for land surface monitoring",
            },
            recommendation=None,
        ),
        ClarifyingQuestion(
            question_id="temporal_res_1",
            question_text="What temporal resolution do you prefer?",
            question_type="resolution_preference",
            options=["16 Day", "Daily", "8 Day"],
            explanations=None,  # No KMS definitions for resolution values
            recommendation=None,
        ),
    ]

    monkeypatch.setattr(
        tool,
        "check_disambiguation",
        lambda cols: (True, disamb_questions),
    )

    monkeypatch.setattr(
        tool,
        "filter_by_user_refinements",
        lambda cols, refs: cols,  # No refinements on initial query
    )

    monkeypatch.setattr(tool, "_describe_search_strategy", lambda *a, **k: "Multi-entity search")

    # === INITIAL QUERY (NO REFINEMENT) ===
    initial_query = DiscoverDataInput(query="I need land cover data")

    initial_output = tool.discover_data(initial_query)

    # Verify initial response
    assert initial_output["status"] == "disambiguation_needed"
    assert len(initial_output["clarifying_questions"]) == 2
    assert initial_output["clarifying_questions"][0]["question_id"] == "platform_pref_1"
    assert len(initial_output["collections"]) == 3
    assert initial_output["total_found"] == 3

    # ========== USER PROVIDES REFINEMENT ANSWERS ==========
    user_refinements = {
        "platform_pref_1": "MODIS (Terra/Aqua)",
        "temporal_res_1": "Moderate (8-16 days)",
    }

    # Create search context from initial response
    search_context = SearchContext(
        temporal=temporal,
        spatial=spatial,
        previous_collection_ids=[
            "G12345_MODIS_1",
            "G12346_LANDSAT_1",
            "G12345_MODIS_via_instr",
        ],
        user_refinements=user_refinements,
        search_iteration=1,
    )

    # ========== FOLLOW-UP QUERY WITH REFINEMENTS ==========
    # Now mock filter_by_user_refinements to apply the refinements
    def filtered_by_refinements(cols, refinements):
        """Filter collections based on user answers."""
        if not refinements:
            return cols

        filtered = cols
        # Apply platform preference
        if "platform_pref_1" in refinements:
            platform_pref = refinements["platform_pref_1"]
            if platform_pref == "MODIS (Terra/Aqua)":
                filtered = [
                    c for c in filtered if "MODIS" in " ".join(c.platforms) or "MODIS" in c.title
                ]
            elif platform_pref == "Landsat":
                filtered = [c for c in filtered if "Landsat" in " ".join(c.platforms)]

        # Apply temporal resolution preference
        if "temporal_res_1" in refinements:
            temp_res = refinements["temporal_res_1"]
            if temp_res == "Moderate (8-16 days)":
                filtered = [
                    c
                    for c in filtered
                    if c.resolution.temporal_resolution_value
                    and 8 <= c.resolution.temporal_resolution_value <= 16
                ]

        return filtered

    monkeypatch.setattr(
        tool,
        "filter_by_user_refinements",
        filtered_by_refinements,
    )

    # After refinement filtering, should only have MODIS collections with 8-16 day resolution
    refined_collections = [
        c
        for c in hydrated_collections
        if ("MODIS" in " ".join(c.platforms) or "MODIS" in c.title)
        and c.resolution.temporal_resolution_value
        and 8 <= c.resolution.temporal_resolution_value <= 16
    ]

    # Mock that after refinement, we no longer need disambiguation
    monkeypatch.setattr(
        tool,
        "check_disambiguation",
        lambda cols: (False, []),
    )

    # Follow-up query with refinements
    followup_query = DiscoverDataInput(
        query="I need land cover data",  # Same query
        previous_context=search_context,
    )

    followup_output = tool.discover_data(followup_query)

    # Verify follow-up response after refinement
    # Status is indirect_matches because we have the via_instrument match
    assert followup_output["status"] == "indirect_matches"
    assert len(followup_output["clarifying_questions"]) == 0
    assert len(followup_output["collections"]) == len(refined_collections)
    # Should have MODIS collections (1 direct + 1 via instrument) with 8-16 day resolution
    for collection in followup_output["collections"]:
        assert "MODIS" in collection["title"] or "MODIS" in str(collection.get("platforms", []))

    # Verify context iteration incremented
    assert followup_output["search_context"]["search_iteration"] == 2
