from pydantic import BaseModel, Field


class CollectionsEmbeddingsInput(BaseModel):
    """
    Input model for collections embeddings queries.

    Validates natural language strings for searching collections using embeddings.
    """

    query: str = Field(
        ...,
        description="A string of text about earth sciences to search collections with using embeddings.",
    )
