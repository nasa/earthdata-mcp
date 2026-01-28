"""Tests for disambiguation utility module."""

import pytest
import responses

from tools.discover_data.utils import disambiguation
from tools.models.output_model import CollectionMatch, ResolutionInfo


@pytest.fixture
def mock_collection():
    """Factory fixture for creating test CollectionMatch objects."""

    def _create(
        concept_id: str = "G1234567890",
        title: str = "Test Collection",
        platforms: list[str] | None = None,
        temporal_resolution: str | None = None,
        spatial_resolution: str | None = None,
    ) -> CollectionMatch:
        resolution = None
        if temporal_resolution or spatial_resolution:
            resolution = ResolutionInfo(
                temporal_resolution=temporal_resolution,
                spatial_resolution=spatial_resolution,
            )
        return CollectionMatch(
            concept_id=concept_id,
            title=title,
            abstract="Test abstract",
            similarity_score=0.9,
            match_type="direct",
            matched_attribute="title",
            resolution=resolution,
            temporal_coverage=None,
            platforms=platforms or [],
            instruments=[],
        )

    return _create


def test_normalize_title_remove_version_patterns():
    """Remove V001, v6.1, Version patterns."""
    assert "test" in disambiguation.normalize_title("Test V001")
    assert "version" not in disambiguation.normalize_title("Test V001").lower()
    assert disambiguation.normalize_title("MODIS V6.1 Data") == "modis data"
    assert disambiguation.normalize_title("Product Version 5") == "product"


def test_normalize_title_remove_resolution_patterns():
    """Remove resolution values like 250m, 1km, 0.25deg."""
    assert "collection" in disambiguation.normalize_title("250m Collection")
    assert "250" not in disambiguation.normalize_title("250m Collection")
    assert disambiguation.normalize_title("Data 1km") == "data"
    assert disambiguation.normalize_title("0.25 degree resolution") == "resolution"


def test_normalize_title_remove_processing_levels():
    """Remove L2, L3, Level 3 patterns."""
    assert disambiguation.normalize_title("Data L2") == "data"
    assert disambiguation.normalize_title("L3 Product") == "product"
    assert disambiguation.normalize_title("Level 2A Data") == "data"


def test_normalize_title_remove_temporal_indicators():
    """Remove Daily, Monthly, 8-Day patterns."""
    assert disambiguation.normalize_title("Daily NDVI") == "ndvi"
    assert disambiguation.normalize_title("Monthly Composite") == "composite"
    assert disambiguation.normalize_title("8-Day Average") == "average"


def test_normalize_title_collapse_whitespace():
    """Collapse multiple spaces and trim."""
    assert disambiguation.normalize_title("Test   Multiple   Spaces") == "test multiple spaces"
    assert disambiguation.normalize_title("  Leading Trailing  ") == "leading trailing"


def test_normalize_title_case_insensitive():
    """Normalize to lowercase."""
    assert disambiguation.normalize_title("TEST COLLECTION") == "test collection"
    assert disambiguation.normalize_title("MoDiS Data") == "modis data"


def test_group_by_normalized_topic_groups_same_topic_different_versions(mock_collection):
    """Collections with same topic but different versions group together."""
    collections = [
        mock_collection(
            concept_id="C1",
            title="MODIS/Terra Surface Reflectance Daily L2G Global 250m SIN Grid V6.0",
        ),
        mock_collection(
            concept_id="C2",
            title="MODIS/Terra Surface Reflectance Daily L2G Global 250m SIN Grid V6.1",
        ),
        mock_collection(
            concept_id="C3",
            title="MODIS/Terra Surface Reflectance Daily L2G Global 250m SIN Grid V7.0",
        ),
    ]

    groups = disambiguation.group_by_normalized_topic(collections)

    assert len(groups) == 1
    # Get the first (and only) group key
    group_key = list(groups.keys())[0]
    assert "modis" in group_key and "surface" in group_key
    assert len(groups[group_key]) == 3


def test_group_by_normalized_topic_groups_by_different_topics(mock_collection):
    """Collections with different topics go to separate groups."""
    collections = [
        mock_collection(
            concept_id="C1",
            title="MODIS/Terra Surface Reflectance Daily L2G Global 250m SIN Grid V6.1",
        ),
        mock_collection(
            concept_id="C2", title="VIIRS/SNPP Surface Reflectance 500m Daily L2 Global"
        ),
        mock_collection(concept_id="C3", title="Landsat 8 Level-2 Science Products"),
    ]

    groups = disambiguation.group_by_normalized_topic(collections)

    assert len(groups) == 3


def test_group_by_normalized_topic_normalizes_resolution_differences(mock_collection):
    """Collections differing only in resolution group together."""
    collections = [
        mock_collection(
            concept_id="C1", title="MODIS/Terra Land Surface Temperature Daily L3 Global 250m Grid"
        ),
        mock_collection(
            concept_id="C2", title="MODIS/Terra Land Surface Temperature Daily L3 Global 1km Grid"
        ),
    ]

    groups = disambiguation.group_by_normalized_topic(collections)

    assert len(groups) == 1
    # Get the first (and only) group key
    group_key = list(groups.keys())[0]
    assert "temperature" in group_key
    assert len(groups[group_key]) == 2


def test_check_disambiguation_no_disambiguation_needed_single_collection(mock_collection):
    """Single collection should not need disambiguation."""
    collections = [mock_collection(concept_id="C1", title="Test")]

    needs_disambiguation, questions = disambiguation.check_disambiguation(collections)

    assert not needs_disambiguation
    assert len(questions) == 0


def test_check_disambiguation_no_disambiguation_same_topic_no_differences(mock_collection):
    """Same topic without differences should not need disambiguation."""
    collections = [
        mock_collection(concept_id="C1", title="MODIS V6"),
        mock_collection(concept_id="C2", title="MODIS V7"),
    ]

    needs_disambiguation, questions = disambiguation.check_disambiguation(collections)

    assert not needs_disambiguation
    assert len(questions) == 0


def test_check_disambiguation_temporal_resolution(mock_collection):
    """Different temporal resolutions should generate a question."""
    collections = [
        mock_collection(
            concept_id="C1",
            title="MODIS/Terra Snow Cover Daily L3 Global 500m Grid V6.1",
            temporal_resolution="Daily",
        ),
        mock_collection(
            concept_id="C2",
            title="MODIS/Terra Snow Cover 8-Day L3 Global 500m Grid V6.1",
            temporal_resolution="8-Day",
        ),
    ]

    needs_disambiguation, questions = disambiguation.check_disambiguation(collections)

    assert needs_disambiguation
    temporal_q = next((q for q in questions if q.question_type == "resolution_preference"), None)
    assert temporal_q is not None
    assert "temporal" in temporal_q.question_id
    assert temporal_q.question_text is not None
    assert len(temporal_q.question_text) > 0
    assert set(temporal_q.options) == {"Daily", "8-Day"}
    assert "snow" in temporal_q.question_text.lower()


def test_check_disambiguation_spatial_resolution(mock_collection):
    """Different spatial resolutions should generate a question."""
    collections = [
        mock_collection(
            concept_id="C1",
            title="MODIS/Terra Vegetation Indices 16-Day L3 Global 250m Grid V6.1",
            spatial_resolution="250m",
        ),
        mock_collection(
            concept_id="C2",
            title="MODIS/Terra Vegetation Indices 16-Day L3 Global 1km Grid V6.1",
            spatial_resolution="1km",
        ),
    ]

    needs_disambiguation, questions = disambiguation.check_disambiguation(collections)

    assert needs_disambiguation
    spatial_q = next((q for q in questions if q.question_type == "resolution_preference"), None)
    assert spatial_q is not None
    assert "spatial" in spatial_q.question_id
    assert spatial_q.question_text is not None
    assert len(spatial_q.question_text) > 0
    assert set(spatial_q.options) == {"250m", "1km"}
    assert "vegetation" in spatial_q.question_text.lower()


def test_check_disambiguation_platform(mock_collection):
    """Different platforms should generate a question."""
    collections = [
        mock_collection(concept_id="C1", title="Data Product", platforms=["Terra"]),
        mock_collection(concept_id="C2", title="Data Product", platforms=["Aqua"]),
    ]

    needs_disambiguation, questions = disambiguation.check_disambiguation(collections)

    assert needs_disambiguation
    platform_q = next((q for q in questions if q.question_type == "platform_preference"), None)
    assert platform_q is not None
    assert platform_q.question_text is not None
    assert len(platform_q.question_text) > 0
    assert (
        "platform" in platform_q.question_text.lower()
        or "satellite" in platform_q.question_text.lower()
    )
    assert set(platform_q.options) == {"Terra", "Aqua"}
    assert platform_q.related_collection_ids == ["C1", "C2"]


def test_check_disambiguation_multiple_types(mock_collection):
    """Detect multiple types of differences."""
    collections = [
        mock_collection(
            concept_id="C1",
            title="MODIS/Terra Surface Reflectance Daily L2G Global 250m SIN Grid V6.1",
            temporal_resolution="Daily",
            spatial_resolution="250m",
            platforms=["Terra"],
        ),
        mock_collection(
            concept_id="C2",
            title="MODIS/Terra Surface Reflectance 8-Day L3 Global 1km SIN Grid V6.1",
            temporal_resolution="8-Day",
            spatial_resolution="1km",
            platforms=["Aqua"],
        ),
    ]

    needs_disambiguation, questions = disambiguation.check_disambiguation(collections)

    assert needs_disambiguation
    assert len(questions) >= 2
    types = [q.question_type for q in questions]
    assert "resolution_preference" in types
    assert "platform_preference" in types


def test_generate_resolution_question_temporal(mock_collection):
    """Temporal resolution question should mention time intervals."""
    collections = [
        mock_collection(concept_id="C1", title="Data Daily", temporal_resolution="Daily"),
        mock_collection(concept_id="C2", title="Data Monthly", temporal_resolution="Monthly"),
    ]
    resolutions = {"Daily", "Monthly"}

    question = disambiguation._generate_resolution_question(
        topic="data",
        resolution_type="temporal",
        resolutions=resolutions,
        collections=collections,
    )

    assert "time intervals" in question.question_text.lower()
    assert "2" in question.question_text
    assert question.question_type == "resolution_preference"
    assert question.question_id is not None
    assert "temporal" in question.question_id.lower()
    assert set(question.options) == resolutions
    assert question.related_collection_ids == ["C1", "C2"]


def test_generate_resolution_question_spatial(mock_collection):
    """Spatial resolution question should mention spatial detail."""
    collections = [
        mock_collection(concept_id="C1", title="Data 250m", spatial_resolution="250m"),
        mock_collection(concept_id="C2", title="Data 1km", spatial_resolution="1km"),
    ]
    resolutions = {"250m", "1km"}

    question = disambiguation._generate_resolution_question(
        topic="data",
        resolution_type="spatial",
        resolutions=resolutions,
        collections=collections,
    )

    assert (
        "spatial" in question.question_text.lower()
        or "resolution" in question.question_text.lower()
    )
    assert question.question_type == "resolution_preference"
    assert question.question_id is not None
    assert "spatial" in question.question_id.lower()
    assert set(question.options) == resolutions
    assert question.related_collection_ids == ["C1", "C2"]


def test_generate_resolution_question_options_sorted(mock_collection):
    """Resolution options should be sorted."""
    collections = [
        mock_collection(concept_id="C1", spatial_resolution="1km"),
        mock_collection(concept_id="C2", spatial_resolution="250m"),
    ]
    resolutions = {"1km", "250m"}

    question = disambiguation._generate_resolution_question(
        topic="data",
        resolution_type="spatial",
        resolutions=resolutions,
        collections=collections,
    )

    assert question.options == sorted(resolutions)


def test_generate_platform_question_text(mock_collection):
    """Platform question should mention satellites."""
    collections = [
        mock_collection(concept_id="C1", platforms=["Terra"]),
        mock_collection(concept_id="C2", platforms=["Aqua"]),
    ]

    question = disambiguation._generate_platform_question(
        topic="test",
        platforms={"Terra", "Aqua"},
        collections=collections,
    )

    assert "platform" in question.question_text.lower()
    assert question.question_type == "platform_preference"
    assert question.question_id is not None
    assert "platform" in question.question_id.lower()
    assert set(question.options) == {"Terra", "Aqua"}
    assert question.related_collection_ids == ["C1", "C2"]


def test_generate_platform_question_options_sorted(mock_collection):
    """Platform options should be sorted."""
    collections = [
        mock_collection(concept_id="C1", platforms=["Aqua"]),
        mock_collection(concept_id="C2", platforms=["Terra"]),
    ]

    question = disambiguation._generate_platform_question(
        topic="test",
        platforms={"Aqua", "Terra"},
        collections=collections,
    )

    assert question.options == ["Aqua", "Terra"]


def test_generate_platform_question_with_kms_definitions(mock_collection, mock_all_requests):
    """Platform question should include KMS definitions when available."""

    # Register mock KMS response for platforms scheme
    mock_all_requests.add(
        responses.GET,
        "https://cmr.earthdata.nasa.gov/kms/concepts/concept_scheme/platforms",
        json={
            "concepts": [
                {
                    "prefLabel": "Terra",
                    "uuid": "terra-uuid",
                    "definitions": [{"text": "Earth Observing System spacecraft"}],
                },
                {
                    "prefLabel": "Unknown",
                    "uuid": "unknown-uuid",
                    "definitions": [],
                },
            ]
        },
        status=200,
    )

    collections = [
        mock_collection(concept_id="C1", platforms=["Terra"]),
        mock_collection(concept_id="C2", platforms=["Unknown"]),
    ]

    question = disambiguation._generate_platform_question(
        topic="test",
        platforms={"Terra", "Unknown"},
        collections=collections,
    )

    assert question.explanations is not None
    assert "Terra" in question.explanations
    # Unknown has no definition
    assert question.explanations.get("Unknown") is None


def test_generate_platform_question_no_explanations_when_none_found(
    mock_collection, mock_all_requests
):
    """Should not include explanations dict if no KMS definitions found."""

    # Register mock KMS response with no definitions
    mock_all_requests.add(
        responses.GET,
        "https://cmr.earthdata.nasa.gov/kms/concepts/concept_scheme/platforms",
        json={
            "concepts": [
                {"prefLabel": "Platform1", "uuid": "p1-uuid", "definitions": []},
                {"prefLabel": "Platform2", "uuid": "p2-uuid", "definitions": []},
            ]
        },
        status=200,
    )

    collections = [
        mock_collection(concept_id="C1", platforms=["Platform1"]),
        mock_collection(concept_id="C2", platforms=["Platform2"]),
    ]

    question = disambiguation._generate_platform_question(
        topic="test",
        platforms={"Platform1", "Platform2"},
        collections=collections,
    )

    assert question.explanations is None


def test_filter_by_user_refinements_no_refinements_returns_all(mock_collection):
    """Empty refinements should return all collections."""
    collections = [
        mock_collection(concept_id="C1"),
        mock_collection(concept_id="C2"),
    ]

    filtered = disambiguation.filter_by_user_refinements(collections, {})

    assert len(filtered) == 2


def test_filter_by_user_refinements_temporal(mock_collection):
    """Filter collections by temporal resolution preference."""
    collections = [
        mock_collection(concept_id="C1", temporal_resolution="Daily"),
        mock_collection(concept_id="C2", temporal_resolution="Monthly"),
    ]

    filtered = disambiguation.filter_by_user_refinements(
        collections,
        {"temporal_res_12345": "Daily"},
    )

    assert len(filtered) == 1
    assert filtered[0].concept_id == "C1"


def test_filter_by_user_refinements_spatial(mock_collection):
    """Filter collections by spatial resolution preference."""
    collections = [
        mock_collection(concept_id="C1", spatial_resolution="250m"),
        mock_collection(concept_id="C2", spatial_resolution="1km"),
    ]

    filtered = disambiguation.filter_by_user_refinements(
        collections,
        {"spatial_res_12345": "1km"},
    )

    assert len(filtered) == 1
    assert filtered[0].concept_id == "C2"


def test_filter_by_user_refinements_platform(mock_collection):
    """Filter collections by platform preference."""
    collections = [
        mock_collection(concept_id="C1", platforms=["Terra"]),
        mock_collection(concept_id="C2", platforms=["Aqua"]),
    ]

    filtered = disambiguation.filter_by_user_refinements(
        collections,
        {"platform_12345": "Terra"},
    )

    assert len(filtered) == 1
    assert filtered[0].concept_id == "C1"


def test_filter_by_user_refinements_multiple(mock_collection):
    """Apply multiple refinements sequentially."""
    collections = [
        mock_collection(
            concept_id="C1",
            temporal_resolution="Daily",
            spatial_resolution="250m",
            platforms=["Terra"],
        ),
        mock_collection(
            concept_id="C2",
            temporal_resolution="Daily",
            spatial_resolution="1km",
            platforms=["Aqua"],
        ),
        mock_collection(
            concept_id="C3",
            temporal_resolution="Monthly",
            spatial_resolution="250m",
            platforms=["Terra"],
        ),
    ]

    filtered = disambiguation.filter_by_user_refinements(
        collections,
        {
            "temporal_res_1": "Daily",
            "spatial_res_2": "250m",
        },
    )

    assert len(filtered) == 1
    assert filtered[0].concept_id == "C1"


def test_filter_by_user_refinements_handles_missing_resolution(mock_collection):
    """Include collections without resolution info."""
    collections = [
        mock_collection(concept_id="C1", temporal_resolution="Daily"),
        mock_collection(concept_id="C2", temporal_resolution=None),
    ]

    filtered = disambiguation.filter_by_user_refinements(
        collections,
        {"temporal_res_1": "Daily"},
    )

    assert len(filtered) == 2


def test_filter_by_user_refinements_handles_empty_platforms(mock_collection):
    """Include collections without platforms."""
    collections = [
        mock_collection(concept_id="C1", platforms=["Terra"]),
        mock_collection(concept_id="C2", platforms=[]),
    ]

    filtered = disambiguation.filter_by_user_refinements(
        collections,
        {"platform_1": "Terra"},
    )

    assert len(filtered) == 2
