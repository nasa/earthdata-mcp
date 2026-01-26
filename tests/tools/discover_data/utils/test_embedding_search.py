"""Tests for embedding_search utilities."""

from tools.discover_data.utils import embedding_search


class _FakeGenerator:
    def __init__(self, vector):
        self.vector = vector
        self.received = None

    def generate(self, query_text: str):
        self.received = query_text
        return self.vector


class _FakeDatastore:
    def __init__(self, results):
        self.results = results
        self.calls = []

    def search_similar(self, *, embedding, limit, entity_type):
        self.calls.append({"embedding": embedding, "limit": limit, "entity_type": entity_type})
        return self.results


def test_get_embedding_generator_lazy_init(monkeypatch):
    class _FakeGen:
        def __init__(self):
            self.created = True

    monkeypatch.setattr(embedding_search, "BedrockEmbeddingGenerator", _FakeGen)
    monkeypatch.setattr(embedding_search, "_embedding_generator", None)

    first = embedding_search.get_embedding_generator()
    second = embedding_search.get_embedding_generator()

    assert isinstance(first, _FakeGen)
    assert first is second


def test_get_datastore_lazy_init(monkeypatch):
    class _FakeStore:
        def __init__(self):
            self.created = True

    monkeypatch.setattr(embedding_search, "PostgresEmbeddingDatastore", _FakeStore)
    monkeypatch.setattr(embedding_search, "_datastore", None)

    first = embedding_search.get_datastore()
    second = embedding_search.get_datastore()

    assert isinstance(first, _FakeStore)
    assert first is second


def test_generate_query_embedding_uses_generator(monkeypatch):
    fake_generator = _FakeGenerator([0.1, 0.2, 0.3])
    monkeypatch.setattr(embedding_search, "get_embedding_generator", lambda: fake_generator)

    result = embedding_search.generate_query_embedding("sea ice")

    assert result == [0.1, 0.2, 0.3]
    assert fake_generator.received == "sea ice"


def test_search_collections_filters_by_threshold_and_entity(monkeypatch):
    fake_generator = _FakeGenerator([0.1, 0.2])
    fake_results = [
        {"type": "collection", "external_id": "C1", "similarity": 0.7},
        {"type": "collection", "external_id": "C2", "similarity": 0.4},
    ]
    fake_datastore = _FakeDatastore(fake_results)

    monkeypatch.setattr(embedding_search, "get_embedding_generator", lambda: fake_generator)
    monkeypatch.setattr(embedding_search, "get_datastore", lambda: fake_datastore)

    filtered = embedding_search.search_collections("snow", similarity_threshold=0.6, limit=5)

    assert filtered == [fake_results[0]]
    assert fake_datastore.calls[0]["entity_type"] == "collection"
    assert fake_datastore.calls[0]["limit"] == 5
    assert fake_datastore.calls[0]["embedding"] == [0.1, 0.2]


def test_search_all_entity_types_filters_and_logs(monkeypatch):
    fake_generator = _FakeGenerator([0.9])
    fake_results = [
        {"type": "variable", "external_id": "V1", "similarity": 0.8},
        {"type": "collection", "external_id": "C1", "similarity": 0.3},
    ]
    fake_datastore = _FakeDatastore(fake_results)

    monkeypatch.setattr(embedding_search, "get_embedding_generator", lambda: fake_generator)
    monkeypatch.setattr(embedding_search, "get_datastore", lambda: fake_datastore)

    filtered = embedding_search.search_all_entity_types("vegetation", similarity_threshold=0.5, limit=10)

    assert filtered == [fake_results[0]]
    assert fake_datastore.calls[0]["entity_type"] is None
    assert fake_datastore.calls[0]["limit"] == 10


def test_search_by_entity_type_respects_type(monkeypatch):
    fake_generator = _FakeGenerator([0.5])
    fake_results = [
        {"type": "platforms", "external_id": "P1", "similarity": 0.9},
        {"type": "platforms", "external_id": "P2", "similarity": 0.4},
    ]
    fake_datastore = _FakeDatastore(fake_results)

    monkeypatch.setattr(embedding_search, "get_embedding_generator", lambda: fake_generator)
    monkeypatch.setattr(embedding_search, "get_datastore", lambda: fake_datastore)

    filtered = embedding_search.search_by_entity_type(
        "aqua",
        entity_type="platforms",
        similarity_threshold=0.6,
        limit=3,
    )

    assert filtered == [fake_results[0]]
    assert fake_datastore.calls[0]["entity_type"] == "platforms"
    assert fake_datastore.calls[0]["limit"] == 3


def test_deduplicate_by_external_id_keeps_highest_and_sorts():
    results = [
        {"external_id": "C1", "similarity": 0.5},
        {"external_id": "C2", "similarity": 0.4},
        {"external_id": "C1", "similarity": 0.9},  # higher duplicate
        {"external_id": "C3", "similarity": 0.7},
    ]

    deduped = embedding_search.deduplicate_by_external_id(results)

    assert deduped == [
        {"external_id": "C1", "similarity": 0.9},
        {"external_id": "C3", "similarity": 0.7},
        {"external_id": "C2", "similarity": 0.4},
    ]
