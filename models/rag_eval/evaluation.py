"""Pydantic models for RAG evaluation."""

from pydantic import BaseModel, Field
from ragas.prompt import PydanticPrompt


class DatasetRelevanceScore(BaseModel):
    """LLM output for dataset relevance scoring"""

    relevance_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Relevance score from 0.0 (not relevant) to 1.0 (highly relevant)",
    )
    reasoning: str = Field(description="Brief explanation of the relevance score")


class DatasetRelevanceInput(BaseModel):
    """Input for dataset relevance evaluation"""

    question: str
    dataset: dict = Field(description="Dataset fields as key-value pairs")


class DatasetRelevancePrompt(PydanticPrompt[DatasetRelevanceInput, DatasetRelevanceScore]):
    """Prompt for evaluating dataset relevance to a user question."""

    instruction = """You are evaluating the relevance of an Earth science dataset to a user's question.

The dataset is provided as a collection of fields. Review all available fields to understand what the dataset contains.

Score the dataset from 0.0 to 1.0 based on how well it matches the user's information need:
- 1.0: Perfect match, directly answers the question
- 0.7-0.9: Highly relevant, contains key information
- 0.4-0.6: Somewhat relevant, partially related
- 0.1-0.3: Loosely related, tangentially relevant
- 0.0: Not relevant at all

Consider: topic match, temporal coverage, spatial coverage, and data type relevance."""

    input_model = DatasetRelevanceInput
    output_model = DatasetRelevanceScore

    examples = [
        (
            DatasetRelevanceInput(
                question="What datasets track sea ice extent in the Arctic?",
                dataset={
                    "title": "MODIS Sea Ice Extent Daily",
                    "abstract": "Daily sea ice extent measurements from MODIS covering polar regions including Arctic and Antarctic from 2000-present.",
                },
            ),
            DatasetRelevanceScore(
                relevance_score=0.95,
                reasoning="Directly matches question - tracks sea ice extent in Arctic with daily measurements",
            ),
        ),
        (
            DatasetRelevanceInput(
                question="What datasets track sea ice extent in the Arctic?",
                dataset={
                    "title": "Global Ocean Temperature Analysis",
                    "abstract": "Monthly global ocean temperature data at various depths from 1950-2023.",
                },
            ),
            DatasetRelevanceScore(
                relevance_score=0.2,
                reasoning="Only tangentially related - ocean temperature affects sea ice but doesn't directly track ice extent",
            ),
        ),
    ]
