"""
Output model for collections embeddings queries.

Defines the structure of search results from CMR collections.
"""

from pydantic import BaseModel, ConfigDict, Field


class DatasetSummary(BaseModel):
    """
    Summary information for a single dataset/collection.
    """

    concept_id: str = Field(
        ...,
        description="The unique CMR concept ID for the collection",
        examples=["C1234567890-PROVIDER"],
    )
    title: str = Field(
        ...,
        description="The title of the collection",
        examples=["MODIS/Terra Surface Reflectance Daily L2G Global 250m SIN Grid V061"],
    )
    abstract: str = Field(
        ...,
        description="A brief abstract or description of the collection",
        examples=["The MODIS Surface Reflectance products provide..."],
    )


class CollectionsEmbeddingsOutput(BaseModel):
    """
    Output model for collections embeddings search results.

    Contains a list of dataset summaries matching the search query.
    """

    results: list[DatasetSummary] = Field(
        default_factory=list,
        description="List of dataset summaries matching the search query",
    )
    count: int = Field(
        default=0,
        description="Total number of results returned",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "results": [
                        {
                            "concept_id": "C1234567890-PROVIDER",
                            "title": "MODIS/Terra Surface Reflectance Daily L2G Global 250m SIN Grid V061",
                            "abstract": "The MODIS Surface Reflectance products provide an estimate of the surface spectral reflectance...",
                        },
                        {
                            "concept_id": "C9876543210-PROVIDER",
                            "title": "VIIRS/NPP Surface Reflectance Daily L2G Global 375m SIN Grid V001",
                            "abstract": "The VIIRS Surface Reflectance products provide an estimate...",
                        },
                    ],
                    "count": 2,
                }
            ]
        }
    )
