"""Test for collection embedding tool"""

from tools.collections_embeddings.tool import search_cmr_collections_embeddings
from tools.collections_embeddings.input_model import CollectionsEmbeddingsInput


def test_returns_not_implemented():
    """Test that function returns NOT IMPLEMENTED YET."""
    input_model = CollectionsEmbeddingsInput(query="ocean temperature")
    result = search_cmr_collections_embeddings(input_model)
    assert result == {"result": "NOT IMPLEMENTED YET", "query": input_model}


def test_returns_not_implemented_empty_query():
    """Test with empty query."""
    input_model = CollectionsEmbeddingsInput(query="")
    result = search_cmr_collections_embeddings(input_model)

    assert result == {"result": "NOT IMPLEMENTED YET", "message": "No query provided"}
