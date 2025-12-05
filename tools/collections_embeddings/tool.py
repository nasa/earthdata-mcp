from typing import Any
from pydantic import BaseModel


class DatasetSummary(BaseModel):
    concept_id: str
    title: str
    abstract: str


def search_cmr_collections_embeddings(
    query: str = "",
) -> Any:
    """Get a list of collections form CMR based on keywords.

    Args:
        keywords: A string of text to search collections with.
    """
    return {"result": "NOT IMPLEMENTED YET"}
