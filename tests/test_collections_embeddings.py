from tools.collections_embeddings.tool import search_cmr_collections_embeddings


def test_returns_not_implemented():
    """Test that function returns NOT IMPLEMENTED YET."""
    result = search_cmr_collections_embeddings(query="ocean temperature")
    assert result == {"result": "NOT IMPLEMENTED YET"}


def test_returns_not_implemented_empty_query():
    """Test with empty query."""
    result = search_cmr_collections_embeddings(query="")
    assert result == {"result": "NOT IMPLEMENTED YET"}
