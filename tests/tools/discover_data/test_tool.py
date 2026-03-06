"""Tests for discover_data orchestrator tool."""

# pylint: disable=too-many-lines
import importlib
from datetime import datetime
from unittest.mock import MagicMock

from models.tools.discover_data import (
    ClarifyingQuestion,
    CollectionMatch,
    DiscoverDataInput,
    ExplorationLink,
    ResolutionInfo,
    SearchContext,
    SpatialConstraint,
    TemporalConstraint,
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
    return importlib.import_module("tools.discover_data.tool")


def test_extract_or_use_constraints_uses_search_context(monkeypatch):
    """Test that search_context constraints are used without re-extraction."""
    tool = _load_tool()

    prior_temporal = TemporalConstraint(
        start_date=datetime(2020, 1, 1), end_date=datetime(2020, 12, 31), reasoning="prev"
    )
    prior_spatial = SpatialConstraint(
        location="test_location",
        wkt_geometry="POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))",
        reasoning="prev",
    )
    prev_ctx = SearchContext(temporal=prior_temporal, spatial=prior_spatial)
    query = DiscoverDataInput(query="q", search_context=prev_ctx)

    # Mock extract_constraints to verify it's NOT called
    extract_called = []
    monkeypatch.setattr(
        tool,
        "extract_constraints",
        lambda q, prior_temporal, prior_spatial: extract_called.append(True)
        or (TemporalConstraint(), SpatialConstraint()),
    )

    temporal, spatial = tool._extract_or_use_constraints(query)

    # Verify extract_constraints was NOT called (avoiding unnecessary extraction)
    assert not extract_called

    # Verify all fields are preserved from search_context
    assert temporal.start_date == prior_temporal.start_date
    assert temporal.end_date == prior_temporal.end_date
    assert temporal.reasoning == "prev"
    assert spatial.location == "test_location"
    assert spatial.wkt_geometry == "POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))"
    assert spatial.reasoning == "prev"


def test_extract_or_use_constraints_extracts_when_missing_context(monkeypatch):
    """Test that extraction happens when search_context is missing or incomplete."""
    tool = _load_tool()

    extracted_temporal = TemporalConstraint(
        start_date=datetime(2021, 6, 1), end_date=None, reasoning="extracted"
    )
    extracted_spatial = SpatialConstraint(
        location="Denver", wkt_geometry="POLYGON((...)", reasoning="extracted"
    )

    # Mock extract_constraints to verify it IS called
    extract_called = []

    def mock_extract(q, prior_temporal, prior_spatial):  # pylint: disable=unused-argument
        extract_called.append(True)
        return extracted_temporal, extracted_spatial

    monkeypatch.setattr(tool, "extract_constraints", mock_extract)

    # Test with no search_context
    query1 = DiscoverDataInput(query="ocean data from 2021")
    temporal1, spatial1 = tool._extract_or_use_constraints(query1)

    assert len(extract_called) == 1
    assert temporal1 == extracted_temporal
    assert spatial1 == extracted_spatial

    # Test with incomplete search_context (only temporal)
    extract_called.clear()
    partial_ctx = SearchContext(temporal=TemporalConstraint(), spatial=None)
    query2 = DiscoverDataInput(query="ocean data", search_context=partial_ctx)
    tool._extract_or_use_constraints(query2)

    assert len(extract_called) == 1

    # Test with incomplete search_context (only spatial)
    extract_called.clear()
    partial_ctx2 = SearchContext(temporal=None, spatial=SpatialConstraint())
    query3 = DiscoverDataInput(query="ocean data", search_context=partial_ctx2)
    tool._extract_or_use_constraints(query3)

    assert len(extract_called) == 1


def test_discover_data_expansion_path(monkeypatch):
    """Test that query expansion path suggests refinement questions."""
    tool = _load_tool()

    temporal = TemporalConstraint()
    spatial = SpatialConstraint()

    monkeypatch.setattr(
        tool,
        "extract_constraints",
        lambda q, prior_temporal, prior_spatial: (temporal, spatial),
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

    def mock_validate_granules(collections, *_args, **_kwargs):
        for col in collections:
            col.granule_count = 100
        return collections

    monkeypatch.setattr(tool, "validate_granule_availability", mock_validate_granules)
    monkeypatch.setattr(tool, "enrich_with_tool_associations", lambda cols, **_kw: cols)

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

    def mock_validate_granules(collections, *_args, **_kwargs):
        for col in collections:
            col.granule_count = 100
        return collections

    monkeypatch.setattr(tool, "validate_granule_availability", mock_validate_granules)
    monkeypatch.setattr(tool, "enrich_with_tool_associations", lambda cols, **_kw: cols)

    # Ensure user refinements are applied
    applied = {}

    def fake_filter_by_user_refinements(cols, refinements):
        applied.update(refinements)
        return cols

    monkeypatch.setattr(tool, "filter_by_user_refinements", fake_filter_by_user_refinements)

    prev_ctx = SearchContext(temporal=None, spatial=None, user_refinements={"a": "b"})
    query = DiscoverDataInput(query="snow", search_context=prev_ctx)

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

    def mock_validate_granules(collections, *_args, **_kwargs):
        for col in collections:
            col.granule_count = 100
        return collections

    monkeypatch.setattr(tool, "validate_granule_availability", mock_validate_granules)
    monkeypatch.setattr(tool, "enrich_with_tool_associations", lambda cols, **_kw: cols)

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

    assert (
        tool._determine_status([], False, [], all_filtered_by_granule_validation=True)
        == tool.DiscoveryStatus.NO_GRANULES_IN_CONSTRAINTS
    )
    assert (
        tool._determine_status([direct], False, [], all_filtered_by_granule_validation=True)
        == tool.DiscoveryStatus.NO_GRANULES_IN_CONSTRAINTS
    )
    assert (
        tool._determine_status([], False, [], all_filtered_by_granule_validation=False)
        == tool.DiscoveryStatus.NO_RESULTS
    )
    assert (
        tool._determine_status([direct], True, [], all_filtered_by_granule_validation=False)
        == tool.DiscoveryStatus.DISAMBIGUATION_NEEDED
    )
    assert (
        tool._determine_status([indirect], False, [], all_filtered_by_granule_validation=False)
        == tool.DiscoveryStatus.INDIRECT_MATCHES
    )
    assert (
        tool._determine_status(
            [direct], False, [{"match_type": "direct"}], all_filtered_by_granule_validation=False
        )
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
    """Discover data should catch unexpected exceptions, return a generic user-facing
    message (not the internal error detail), and set status to error."""
    tool = _load_tool()

    # Create a mock that raises an exception
    def raise_error(*args, **kwargs):
        raise RuntimeError("Extraction failed")

    monkeypatch.setattr(tool, "extract_constraints", raise_error)
    query = DiscoverDataInput(query="test")

    output = tool.discover_data(query)

    assert output["status"] == "error"
    assert output["error_message"] == "An unexpected error occurred. Please try your request again."
    # Internal error detail must not be exposed to the caller
    assert "Extraction failed" not in output["error_message"]


def test_discover_data_granule_validation_error(monkeypatch):
    """GranuleValidationError from validate_granule_availability should produce a
    specific user-facing message distinct from the generic error handler."""
    from tools.discover_data.utils.granule_availability import GranuleValidationError

    tool = _load_tool()

    temporal = TemporalConstraint(start_date=datetime(2020, 1, 1), end_date=datetime(2020, 12, 31))
    spatial = SpatialConstraint()

    monkeypatch.setattr(tool, "extract_constraints", lambda *_, **__: (temporal, spatial))
    monkeypatch.setattr(tool, "search_all_entity_types", lambda *_, **__: [])
    monkeypatch.setattr(tool, "score_and_rank_collections", lambda *_, **__: [])
    monkeypatch.setattr(tool, "hydrate_collections", lambda *_, **__: [_make_collection("C1")])

    def _raise_granule_error(*_):
        raise GranuleValidationError("CMR granule validation failed for 1 of 1 collection(s)")

    monkeypatch.setattr(tool, "validate_granule_availability", _raise_granule_error)

    output = tool.discover_data(DiscoverDataInput(query="test"))

    assert output["status"] == "error"
    assert output["error_message"] == (
        "Granule availability check failed due to a service error. Please try your request again."
    )
    # Internal CMR detail must not be exposed to the caller
    assert "CMR" not in output["error_message"]


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
        lambda q, prior_temporal, prior_spatial: (temporal, spatial),
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

    def mock_validate_granules(collections, *_args, **_kwargs):
        for col in collections:
            col.granule_count = 100
        return collections

    monkeypatch.setattr(tool, "validate_granule_availability", mock_validate_granules)
    monkeypatch.setattr(tool, "enrich_with_tool_associations", lambda cols, **_kw: cols)

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
        lambda q, prior_temporal, prior_spatial: (temporal, spatial),
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
                "Aqua": (
                    "NASA satellite launched in 2002 carrying MODIS and other "
                    "instruments for studying Earth's water cycle and clouds"
                ),
                "Terra": (
                    "NASA satellite launched in 1999 carrying MODIS and other "
                    "instruments for observing Earth's land, atmosphere, and oceans"
                ),
                "Landsat-8": (
                    "USGS/NASA satellite launched in 2013 providing multispectral "
                    "imagery with 30m resolution for land surface monitoring"
                ),
                "Landsat-9": (
                    "USGS/NASA satellite launched in 2021 providing improved "
                    "multispectral imagery with 30m resolution for land surface monitoring"
                ),
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

    def mock_validate_granules(collections, *_args, **_kwargs):
        for col in collections:
            col.granule_count = 100
        return collections

    monkeypatch.setattr(tool, "validate_granule_availability", mock_validate_granules)
    monkeypatch.setattr(tool, "enrich_with_tool_associations", lambda cols, **_kw: cols)

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
        search_context=search_context,
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


def test_discover_data_with_granule_validation(monkeypatch):
    """Test that granule validation phase filters out collections without granules."""
    tool = _load_tool()

    temporal = TemporalConstraint(start_date=datetime(2023, 1, 1), end_date=datetime(2023, 12, 31))
    spatial = SpatialConstraint(wkt_geometry="POLYGON((0 0,1 0,1 1,0 1,0 0))")

    monkeypatch.setattr(tool, "extract_constraints", lambda *_args, **_kwargs: (temporal, spatial))
    monkeypatch.setattr(
        tool,
        "search_all_entity_types",
        lambda *_args, **_kwargs: [
            {"type": "collection", "similarity": 0.8, "match_type": "direct"}
        ],
    )

    # Return two collections from hydration
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
    monkeypatch.setattr(tool, "filter_by_user_refinements", lambda cols, refs: cols)

    # Mock validate_granule_availability to return only C1 (C2 filtered out)
    def mock_validate(cols, _temporal, _spatial, _wkt):
        return [c for c in cols if c.concept_id == "C1"]

    monkeypatch.setattr(tool, "validate_granule_availability", mock_validate)
    monkeypatch.setattr(tool, "enrich_with_tool_associations", lambda cols, **_kw: cols)

    query = DiscoverDataInput(query="ocean data")
    output = tool.discover_data(query)

    assert output["status"] == "collections_found"
    assert len(output["collections"]) == 1
    assert output["collections"][0]["concept_id"] == "C1"


def test_discover_data_all_filtered_by_granule_validation(monkeypatch):
    """Test NO_GRANULES_IN_CONSTRAINTS when all collections filtered by validation."""
    tool = _load_tool()

    temporal = TemporalConstraint(start_date=datetime(2023, 1, 1), end_date=datetime(2023, 12, 31))
    spatial = SpatialConstraint(wkt_geometry="POLYGON((0 0,1 0,1 1,0 1,0 0))")

    monkeypatch.setattr(tool, "extract_constraints", lambda *_args, **_kwargs: (temporal, spatial))
    monkeypatch.setattr(
        tool,
        "search_all_entity_types",
        lambda *_args, **_kwargs: [
            {"type": "collection", "similarity": 0.8, "match_type": "direct"}
        ],
    )

    # Return collections from hydration
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
    monkeypatch.setattr(tool, "filter_by_user_refinements", lambda cols, refs: cols)

    monkeypatch.setattr(tool, "validate_granule_availability", lambda *args: [])

    query = DiscoverDataInput(query="ocean data")
    output = tool.discover_data(query)

    assert output["status"] == "no_granules_in_constraints"
    assert not output["collections"]


def test_discover_data_tool_association_error(monkeypatch):
    """ToolAssociationError should produce a specific user-facing error message."""
    from tools.discover_data.utils.tool_associations import ToolAssociationError

    tool = _load_tool()

    temporal = TemporalConstraint()
    spatial = SpatialConstraint()

    monkeypatch.setattr(tool, "extract_constraints", lambda *_, **__: (temporal, spatial))
    monkeypatch.setattr(tool, "search_all_entity_types", lambda *_, **__: [])
    monkeypatch.setattr(tool, "score_and_rank_collections", lambda *_, **__: [])
    monkeypatch.setattr(tool, "hydrate_collections", lambda *_, **__: [_make_collection("C1")])

    def _mock_validate(collections, *_args, **_kwargs):
        for col in collections:
            col.granule_count = 100
        return collections

    monkeypatch.setattr(tool, "validate_granule_availability", _mock_validate)
    monkeypatch.setattr(
        tool,
        "enrich_with_tool_associations",
        MagicMock(side_effect=ToolAssociationError("CMR tool fetch failed for C1")),
    )

    output = tool.discover_data(DiscoverDataInput(query="test"))

    assert output["status"] == "error"
    assert output["error_message"] == (
        "Tool association enrichment failed due to a service error. "
        "Please try your request again."
    )
    # Internal error detail must not be exposed to the caller
    assert "CMR" not in output["error_message"]


def test_discover_data_calls_enrich_with_tool_associations(monkeypatch):
    """enrich_with_tool_associations should be called with the validated collections."""
    tool = _load_tool()

    temporal = TemporalConstraint()
    spatial = SpatialConstraint()
    collection = _make_collection("C1")

    monkeypatch.setattr(tool, "extract_constraints", lambda *_, **__: (temporal, spatial))
    monkeypatch.setattr(tool, "search_all_entity_types", lambda *_, **__: [])
    monkeypatch.setattr(
        tool, "score_and_rank_collections", lambda *_, **__: [_make_collection_dict("C1")]
    )
    monkeypatch.setattr(tool, "hydrate_collections", lambda *_, **__: [collection])

    def _mock_validate(collections, *_args, **_kwargs):
        for col in collections:
            col.granule_count = 50
        return collections

    monkeypatch.setattr(tool, "validate_granule_availability", _mock_validate)
    monkeypatch.setattr(tool, "should_expand_query", lambda *_, **__: False)
    monkeypatch.setattr(tool, "check_disambiguation", lambda cols: (False, []))
    monkeypatch.setattr(tool, "_describe_search_strategy", lambda *a, **k: "desc")

    enriched_with = []

    def _capture_enrich(cols, **_kw):
        enriched_with.extend(cols)
        return cols

    monkeypatch.setattr(tool, "enrich_with_tool_associations", _capture_enrich)

    tool.discover_data(DiscoverDataInput(query="snow cover"))

    assert len(enriched_with) == 1
    assert enriched_with[0].concept_id == "C1"


def test_discover_data_skips_enrichment_when_all_granule_filtered(monkeypatch):
    """enrich_with_tool_associations should NOT be called when all collections are
    filtered out by granule validation (all_filtered_by_granule_validation=True)."""
    tool = _load_tool()

    temporal = TemporalConstraint()
    spatial = SpatialConstraint()

    monkeypatch.setattr(tool, "extract_constraints", lambda *_, **__: (temporal, spatial))
    monkeypatch.setattr(tool, "search_all_entity_types", lambda *_, **__: [])
    monkeypatch.setattr(
        tool,
        "score_and_rank_collections",
        lambda *_, **__: [_make_collection_dict("C1"), _make_collection_dict("C2")],
    )
    monkeypatch.setattr(
        tool,
        "hydrate_collections",
        lambda *_, **__: [_make_collection("C1"), _make_collection("C2")],
    )
    # All collections filtered → all_filtered_by_granule_validation = True
    monkeypatch.setattr(tool, "validate_granule_availability", lambda *_: [])
    monkeypatch.setattr(tool, "_describe_search_strategy", lambda *a, **k: "desc")
    monkeypatch.setattr(tool, "should_expand_query", lambda *_, **__: False)
    monkeypatch.setattr(tool, "check_disambiguation", lambda cols: (False, []))

    enrich_called = []
    monkeypatch.setattr(
        tool,
        "enrich_with_tool_associations",
        lambda cols, **_kw: enrich_called.append(cols) or cols,
    )

    output = tool.discover_data(DiscoverDataInput(query="test"))

    assert output["status"] == "no_granules_in_constraints"
    assert not enrich_called


def test_discover_data_enriched_tool_associations_appear_in_output(monkeypatch):
    """Tool associations populated by enrichment should be present in the final output."""
    tool = _load_tool()

    temporal = TemporalConstraint()
    spatial = SpatialConstraint()
    collection = _make_collection("C1")

    monkeypatch.setattr(tool, "extract_constraints", lambda *_, **__: (temporal, spatial))
    monkeypatch.setattr(tool, "search_all_entity_types", lambda *_, **__: [])
    monkeypatch.setattr(
        tool, "score_and_rank_collections", lambda *_, **__: [_make_collection_dict("C1")]
    )
    monkeypatch.setattr(tool, "hydrate_collections", lambda *_, **__: [collection])

    def _mock_validate(collections, *_args, **_kwargs):
        for col in collections:
            col.granule_count = 10
        return collections

    monkeypatch.setattr(tool, "validate_granule_availability", _mock_validate)
    monkeypatch.setattr(tool, "should_expand_query", lambda *_, **__: False)
    monkeypatch.setattr(tool, "check_disambiguation", lambda cols: (False, []))
    monkeypatch.setattr(tool, "_describe_search_strategy", lambda *a, **k: "desc")

    tools_payload = [ExplorationLink(name="Earthdata Search", url="https://x")]

    def _mock_enrich(cols, **_kw):
        for col in cols:
            col.exploration_links = tools_payload
        return cols

    monkeypatch.setattr(tool, "enrich_with_tool_associations", _mock_enrich)

    output = tool.discover_data(DiscoverDataInput(query="vegetation index"))

    assert len(output["collections"]) == 1
    assert output["collections"][0]["exploration_links"] == [
        {"name": "Earthdata Search", "url": "https://x", "topic": None}
    ]
