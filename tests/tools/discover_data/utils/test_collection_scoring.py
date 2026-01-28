"""Tests for collection_scoring utility module."""

import pytest

from tools.discover_data.utils import collection_scoring


def test_direct_collection_scores_and_ranks(monkeypatch):
    """Direct collection matches should carry through with direct match_type."""

    def fake_lookup(_entities):
        return {}

    monkeypatch.setattr(collection_scoring, "get_collections_for_entities", fake_lookup)

    embedding_results = [
        {
            "type": "collection",
            "external_id": "C1",
            "similarity": 0.9,
            "attribute": "title",
            "text_content": "foo",
        }
    ]

    ranked = collection_scoring.score_and_rank_collections(
        embedding_results, similarity_threshold=0.1
    )

    assert [r["external_id"] for r in ranked] == ["C1"]
    assert ranked[0]["match_type"] == "direct"
    # direct_score * DIRECT_WEIGHT (1.0)
    assert ranked[0]["similarity"] == pytest.approx(0.9 * collection_scoring.DIRECT_WEIGHT)
    assert ranked[0]["attribute"] == "title"
    assert ranked[0]["text_content"] == "foo"


def test_indirect_scores_apply_weights_and_diminishing(monkeypatch):
    """Indirect signals use type weights and diminishing returns, then weighted by INDIRECT_WEIGHT."""

    def fake_lookup(entities):
        assert set(entities) == {("var-1", "variable"), ("cit-1", "citation")}
        return {"var-1": ["C1"], "cit-1": ["C1"]}

    monkeypatch.setattr(collection_scoring, "get_collections_for_entities", fake_lookup)

    embedding_results = [
        {"type": "variable", "external_id": "var-1", "similarity": 1.0, "text_content": "var text"},
        {"type": "citation", "external_id": "cit-1", "similarity": 0.5, "text_content": "cit text"},
    ]

    ranked = collection_scoring.score_and_rank_collections(
        embedding_results, similarity_threshold=0.0
    )

    assert [r["external_id"] for r in ranked] == ["C1"]
    # weighted scores: 1.0*1.0, 0.5*0.8=0.4; diminishing: 1.0 + 0.4/2 = 1.2; * INDIRECT_WEIGHT (0.8) = 0.96
    assert ranked[0]["similarity"] == pytest.approx(0.96)
    assert ranked[0]["match_type"] == "via_variable"
    assert ranked[0]["related_entity_id"] == "var-1"
    assert "var text" in ranked[0].get("related_entity_text", "")


def test_direct_and_indirect_combined_and_threshold(monkeypatch):
    """Combined score should include direct + indirect and respect threshold filter."""

    def fake_lookup(entities):
        assert set(entities) == {("var-1", "variable")}
        return {"var-1": ["C1"]}

    monkeypatch.setattr(collection_scoring, "get_collections_for_entities", fake_lookup)

    embedding_results = [
        {"type": "collection", "external_id": "C1", "similarity": 0.2},
        {"type": "variable", "external_id": "var-1", "similarity": 1.0, "text_content": "var"},
    ]

    ranked = collection_scoring.score_and_rank_collections(
        embedding_results, similarity_threshold=0.5
    )

    # indirect weighted: 1.0 * 1.0 =1.0 -> diminishing 1.0 -> *0.8 =0.8; direct 0.2*1=0.2; combined=1.0
    assert [r["external_id"] for r in ranked] == ["C1"]
    assert ranked[0]["similarity"] == pytest.approx(1.0)
    assert ranked[0]["match_type"] == "direct_and_indirect"


def test_explain_collection_ranking_includes_components():
    """Explanation should mention direct, indirect signals, and combined score."""
    score = collection_scoring.CollectionScore(
        collection_id="C1", direct_score=0.5, direct_text="foo", direct_attribute="title"
    )
    score.add_indirect_signal(
        entity_id="var-1", entity_type="variable", entity_text="bar", similarity=0.8
    )
    score.compute_combined_score()

    explanation = collection_scoring.explain_collection_ranking(score)

    assert "Direct match" in explanation
    assert "indirect signal" in explanation
    assert "Combined score" in explanation
    assert "variable" in explanation


def test_unknown_match_type_when_no_signals():
    """When there are no direct or indirect signals, match_type should be unknown and best_indirect None."""
    score = collection_scoring.CollectionScore(collection_id="C0")
    score.compute_combined_score()

    result = score.to_embedding_result()

    assert result["match_type"] == "unknown"
    assert score.best_indirect is None
    assert score.num_signals == 0
