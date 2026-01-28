"""Tests for association_search utility module."""

import pytest

from tools.discover_data.utils import association_search
from util import datastores


@pytest.fixture(autouse=True)
def reset_datastore_singleton():
    """Ensure the shared datastore singleton is reset between tests."""
    datastores.reset_datastore()
    yield
    datastores.reset_datastore()


def test_get_collections_for_entities_uses_datastore(monkeypatch):
    """Ensure get_collections_for_entities delegates to the datastore singleton."""
    calls: list[list[tuple[str, str]]] = []

    class FakeDatastore:
        """Mock datastore for testing collections for entities."""

        def get_collections_for_entities(self, entities):
            """Mock get_collections_for_entities method."""
            calls.append(list(entities))
            return {"cit-1": ["C1"], "var-1": ["C2", "C3"]}

    fake = FakeDatastore()
    monkeypatch.setattr(datastores, "_datastore", fake)

    entities = [("cit-1", "citation"), ("var-1", "variable")]
    result = association_search.get_collections_for_entities(entities)

    assert result == {"cit-1": ["C1"], "var-1": ["C2", "C3"]}
    assert calls == [entities]


def test_get_collections_for_entities_empty(monkeypatch):
    """Empty entities input should short-circuit to an empty dict."""
    calls: list[list[tuple[str, str]]] = []

    class FakeDatastore:
        """Mock datastore for testing empty entities handling."""

        def get_collections_for_entities(self, entities):
            """Mock implementation for testing."""
            calls.append(list(entities))
            return {"cit-1": ["C1"]}

    fake = FakeDatastore()
    monkeypatch.setattr(datastores, "_datastore", fake)

    result = association_search.get_collections_for_entities([])

    assert result == {}
    assert not calls  # Datastore should not be called for empty input


def test_enrich_indirect_matches_adds_associations(monkeypatch):
    """Non-collection results should be enriched with associated collections."""
    monkeypatch.setattr(
        association_search,
        "get_collections_for_entities",
        lambda entities: {"cit-1": ["C1", "C2"], "var-1": ["C3"]},
    )

    embedding_results = [
        {"type": "collection", "external_id": "C0", "similarity": 0.9},
        {"type": "citation", "external_id": "cit-1", "similarity": 0.8},
        {"type": "variable", "external_id": "var-1", "similarity": 0.7},
    ]

    enriched = association_search.enrich_indirect_matches(embedding_results)

    collection = next(r for r in enriched if r["type"] == "collection")
    citation = next(r for r in enriched if r["type"] == "citation")
    variable = next(r for r in enriched if r["type"] == "variable")

    assert "associated_collections" not in collection
    assert citation["associated_collections"] == ["C1", "C2"]
    assert variable["associated_collections"] == ["C3"]


def test_enrich_indirect_matches_no_non_collections(monkeypatch):
    """If there are no non-collection results, pass through unchanged."""
    monkeypatch.setattr(
        association_search, "get_collections_for_entities", lambda entities: {"cit-1": ["C1"]}
    )

    embedding_results = [
        {"type": "collection", "external_id": "C0", "similarity": 0.9},
        {"type": "collection", "external_id": "C1", "similarity": 0.8},
    ]

    enriched = association_search.enrich_indirect_matches(embedding_results)

    assert enriched == embedding_results


def test_expand_to_collections_converts_non_collections(monkeypatch):
    """Expand non-collection results into collection records with match_type metadata."""
    monkeypatch.setattr(
        association_search,
        "get_collections_for_entities",
        lambda entities: {"cit-1": ["C1"], "var-1": ["C2"]},
    )

    embedding_results = [
        {
            "type": "collection",
            "external_id": "C0",
            "attribute": "title",
            "text_content": "foo",
            "similarity": 0.9,
        },
        {"type": "citation", "external_id": "cit-1", "text_content": "cite", "similarity": 0.8},
        {"type": "variable", "external_id": "var-1", "text_content": "var", "similarity": 0.7},
    ]

    collections = association_search.expand_to_collections(embedding_results)

    # Should produce three unique collections, sorted by similarity
    assert [c["external_id"] for c in collections] == ["C0", "C1", "C2"]

    direct = next(c for c in collections if c["external_id"] == "C0")
    via_citation = next(c for c in collections if c["external_id"] == "C1")
    via_variable = next(c for c in collections if c["external_id"] == "C2")

    assert direct["match_type"] == "direct"
    assert direct["related_entity_id"] is None
    assert via_citation["match_type"] == "via_citation"
    assert via_citation["related_entity_id"] == "cit-1"
    assert via_variable["match_type"] == "via_variable"
    assert via_variable["related_entity_id"] == "var-1"
