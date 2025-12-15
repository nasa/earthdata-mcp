from typing import Any
from pydantic import BaseModel
from schemas.collections_embeddings.input_model import CollectionsEmbeddingsInput


class DatasetSummary(BaseModel):
    concept_id: str
    title: str
    abstract: str


def search_cmr_collections_embeddings(
    query: CollectionsEmbeddingsInput,
) -> Any:
    """Get a list of collections from CMR based on embeddings search.

    Args:
        query: A string of text to search collections with using embeddings.

    Returns:
        A list of dictionaries containing dataset summaries with concept_id, title, and abstract.
    """
    return {"result": "NOT IMPLEMENTED YET"}
