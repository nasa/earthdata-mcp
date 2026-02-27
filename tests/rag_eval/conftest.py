"""Pytest fixtures for RAG evaluation tests."""

import pytest


@pytest.fixture
def sample_collections():
    """Sample collection dictionaries for testing."""
    return [
        {
            "id": "C1234-TEST",
            "title": "Arctic Sea Ice Concentration Dataset",
            "abstract": "Daily sea ice concentration data from Arctic region derived from satellite observations.",
            "score": 0.95,
        },
        {
            "id": "C5678-TEST",
            "title": "Global Temperature Anomalies",
            "abstract": "Monthly global temperature anomaly data showing deviations from long-term mean.",
            "score": 0.82,
        },
        {
            "id": "C9012-TEST",
            "title": "Ocean Salinity Measurements",
            "abstract": "In-situ ocean salinity measurements collected from buoys and research vessels.",
            "score": 0.71,
        },
    ]


@pytest.fixture
def sample_question():
    """Sample user question for testing."""
    return "What datasets are available for Arctic sea ice concentration?"


@pytest.fixture
def sample_contexts():
    """Sample formatted contexts for testing."""
    return [
        "Title: Arctic Sea Ice Concentration Dataset\nAbstract: Daily sea ice concentration data from Arctic region derived from satellite observations.",
        "Title: Global Temperature Anomalies\nAbstract: Monthly global temperature anomaly data showing deviations from long-term mean.",
        "Title: Ocean Salinity Measurements\nAbstract: In-situ ocean salinity measurements collected from buoys and research vessels.",
    ]


@pytest.fixture
def sample_answer():
    """Sample generated answer for testing."""
    return (
        "Found 3 relevant data collections. "
        "Top matches include: Arctic Sea Ice Concentration Dataset, "
        "Global Temperature Anomalies, Ocean Salinity Measurements."
    )


@pytest.fixture
def mock_langfuse_client(mocker):
    """Mock Langfuse client."""
    mock_client = mocker.MagicMock()
    mock_dataset = mocker.MagicMock()
    mock_dataset.items = []
    mock_client.get_dataset.return_value = mock_dataset
    return mock_client


@pytest.fixture
def mock_dataset_item():
    """Mock Langfuse dataset item."""

    class MockDatasetItem:
        """Mock class for Langfuse dataset items."""

        def __init__(self, question):
            self.input = {"question": question}
            self.id = "test-item-1"

    return MockDatasetItem("What is Arctic sea ice?")


@pytest.fixture
def mock_bedrock_llm(mocker):
    """Mock Bedrock LLM for testing."""
    mock_llm = mocker.MagicMock()
    mock_llm.model_name = "amazon.nova-pro-v1:0"
    return mock_llm


@pytest.fixture
def mock_bedrock_embeddings(mocker):
    """Mock Bedrock embeddings for testing."""
    mock_embeddings = mocker.MagicMock()
    return mock_embeddings


@pytest.fixture
def mock_ragas_scores():
    """Mock Ragas evaluation scores."""
    return {
        "faithfulness": 0.85,
        "context_precision": 0.78,
    }


@pytest.fixture
def mock_relevance_result(mocker):
    """Mock relevance prompt result."""
    result = mocker.MagicMock()
    result.relevance_score = 0.9
    result.reasoning = "Highly relevant to the query"
    return result


@pytest.fixture
def mock_mcp_response():
    """Mock MCP server response."""
    return {
        "answer": "Found 3 relevant collections.",
        "raw_result": {
            "collections": [
                {
                    "id": "C1234-TEST",
                    "title": "Arctic Sea Ice",
                    "abstract": "Sea ice data",
                }
            ]
        },
    }
