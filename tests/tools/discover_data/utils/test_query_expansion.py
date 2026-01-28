"""Tests for query_expansion utilities."""

from tools.discover_data.utils import query_expansion


def test_analyze_embedding_results_categorizes_and_filters():
    """Verify embedding results are categorized by type and filtered by similarity threshold."""
    embedding_results = [
        {
            "type": "collection",
            "external_id": "C1",
            "text_content": "collection text",
            "similarity": 0.31,
        },
        {
            "type": "sciencekeywords",
            "external_id": "K1",
            "text_content": "Atmosphere > Clouds",
            "similarity": 0.35,
        },
        {
            "type": "instruments",
            "external_id": "I1",
            "text_content": "MODIS instrument",
            "similarity": 0.4,
        },
        {"type": "platforms", "external_id": "P1", "text_content": "Terra", "similarity": 0.45},
        {
            "type": "variable",
            "external_id": "V1",
            "text_content": "NDVI vegetation index",
            "similarity": 0.5,
        },
        {
            "type": "collection",
            "external_id": "C2",
            "text_content": "low sim",
            "similarity": 0.2,
        },  # filtered out
    ]

    ctx = query_expansion.analyze_embedding_results(embedding_results, min_similarity=0.3)

    assert len(ctx.weak_collection_matches) == 1
    assert len(ctx.science_keywords) == 1
    assert len(ctx.instruments) == 1
    assert len(ctx.platforms) == 1
    assert len(ctx.variables) == 1


def test_analyze_embedding_results_truncates_text():
    """Verify long text content is truncated to 200 character limit."""
    long_text = "X" * 300
    embedding_results = [
        {"type": "collection", "external_id": "C1", "text_content": long_text, "similarity": 0.5}
    ]

    ctx = query_expansion.analyze_embedding_results(embedding_results)

    assert len(ctx.weak_collection_matches[0]["text"]) == 200


def test_generate_expansion_questions_builds_expected_prompts():
    """Verify expansion questions are generated with correct options from discovery context."""
    ctx = query_expansion.DiscoveryContext(
        science_keywords=[{"text": "Atmosphere > Clouds"}, {"text": "Ocean > Waves"}],
        instruments=[{"text": "MODIS: Moderate Resolution"}, {"text": "VIIRS"}],
        variables=[{"text": "Chlorophyll concentration"}, {"text": "Sea surface temperature"}],
        available_temporal_resolutions={"Daily", "8-Day", "Monthly"},
    )

    questions = query_expansion.generate_expansion_questions("ocean color", ctx)

    q_types = {q.question_id: q for q in questions}

    assert "data_type" in q_types
    assert q_types["data_type"].question_type == "data_type_preference"
    assert sorted(q_types["data_type"].options) == ["Clouds", "Waves"]

    assert "instrument_preference" in q_types
    assert set(q_types["instrument_preference"].options) == {"MODIS", "VIIRS"}

    assert "temporal_resolution" in q_types
    assert q_types["temporal_resolution"].options == ["8-Day", "Daily", "Monthly"]
    assert "Daily" in q_types["temporal_resolution"].explanations

    assert "variable_preference" in q_types
    assert set(q_types["variable_preference"].options) == {
        "Chlorophyll concentration",
        "Sea surface temperature",
    }


def test_generate_expansion_questions_limits_temporal_options_to_four():
    """Verify temporal resolution options are limited to maximum of four choices."""
    ctx = query_expansion.DiscoveryContext(
        available_temporal_resolutions={"Daily", "8-Day", "Monthly", "Yearly", "Quarterly"},
    )

    questions = query_expansion.generate_expansion_questions("climate", ctx)

    temporal = next(q for q in questions if q.question_id == "temporal_resolution")
    assert len(temporal.options) == 4  # limited


def test_extract_keyword_options_parses_hierarchy_and_words():
    """Verify keyword extraction handles both hierarchy (>) and space-separated text."""
    keywords = [
        {"text": "Atmosphere > Clouds"},
        {"text": "Ocean Waves"},
    ]

    options = query_expansion._extract_keyword_options(keywords)

    assert options == ["Clouds", "Ocean Waves"]


def test_extract_name_from_text_formats_correctly():
    """Verify text extraction handles abbreviations, full text, and empty strings."""
    assert query_expansion._extract_name_from_text("MODIS: Moderate Resolution") == "MODIS"
    assert (
        query_expansion._extract_name_from_text("Sea surface temperature anomaly")
        == "Sea surface temperature"
    )
    assert query_expansion._extract_name_from_text("") == "Unknown"


def test_should_expand_query_true_with_related_entities():
    """Verify query should expand when related entities with high similarity are found."""
    scored = []
    embedding_results = [
        {"type": "sciencekeywords", "similarity": 0.4},
        {"type": "instruments", "similarity": 0.35},
        {"type": "collection", "similarity": 0.2},
    ]

    assert (
        query_expansion.should_expand_query(scored, embedding_results, confidence_threshold=0.5)
        is True
    )


def test_should_expand_query_false_when_enough_collections():
    """Verify query should not expand when enough collection results already exist."""
    scored = [{}, {}, {}]
    embedding_results = [
        {"type": "sciencekeywords", "similarity": 0.5},
        {"type": "instruments", "similarity": 0.5},
    ]

    assert query_expansion.should_expand_query(scored, embedding_results) is False


def test_should_expand_query_false_when_not_enough_related():
    """Verify query should not expand when related entities below similarity threshold."""
    scored = []
    embedding_results = [
        {"type": "instruments", "similarity": 0.29},  # below 0.3
        {"type": "collection", "similarity": 0.9},
    ]

    assert query_expansion.should_expand_query(scored, embedding_results) is False
