"""Input model for collections embeddings tool."""

from pydantic import BaseModel, Field


class CollectionsEmbeddingsInput(BaseModel):
    """Input model for collections embeddings queries."""

    query: str = Field(
        ...,
        description="Natural language text to search collections using embeddings.",
    )
