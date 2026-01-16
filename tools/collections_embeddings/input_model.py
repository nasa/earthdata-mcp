from pydantic import BaseModel, Field


class CollectionsEmbeddingsInput(BaseModel):
    """
    Input model for collections embeddings queries.

    Validates natural language strings for searching collections using embeddings.
    """

    query: str = Field(
        ...,
        description="Natural language query to search NASA Earth science datasets (e.g., 'atmospheric temperature data' or 'ocean color measurements').",
    )
