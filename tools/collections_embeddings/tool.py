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
    output = [
        DatasetSummary(
            concept_id="NOT IMPLEMENTED YET",
            title="NOT IMPLEMENTED YET",
            abstract="NOT IMPLEMENTED YET",
        )
    ]

    # Convert Pydantic models to dicts
    return [ds.model_dump() for ds in output]
