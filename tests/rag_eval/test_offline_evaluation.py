"""Tests for offline RAG evaluation (rag_eval/evals.py)."""

import os
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

from rag_eval.evals import (
    EarthdataEvaluator,
    SingleEvaluation,
)
from util.rag_eval.collection_formatting import (
    format_collection_context,
    generate_contexts_from_collections,
    generate_answer_from_collections,
)


# === Utility Function Tests ===


class TestUtilityFunctions:
    """Test utility functions for context generation."""

    def test_format_collection_context(self, sample_collections):
        """Test formatting a single collection into context string."""
        collection = sample_collections[0]
        fields = ["title", "abstract"]

        result = format_collection_context(collection, fields)

        assert "Title: Arctic Sea Ice Concentration Dataset" in result
        assert "Abstract: Daily sea ice concentration data" in result
        assert "\n" in result  # Multi-line format

    def test_format_collection_context_missing_field(self):
        """Test handling of missing fields in collection."""
        collection = {"title": "Test Dataset"}
        fields = ["title", "abstract", "nonexistent"]

        result = format_collection_context(collection, fields)

        assert "Title: Test Dataset" in result
        assert "Abstract:" not in result  # Missing field should be skipped
        assert "Nonexistent:" not in result

    def test_format_collection_context_empty_fields(self, sample_collections):
        """Test formatting with empty field list."""
        result = format_collection_context(sample_collections[0], [])
        assert result == ""

    def test_generate_contexts_from_collections(self, sample_collections):
        """Test generating contexts from multiple collections."""
        fields = ["title", "abstract"]

        contexts = generate_contexts_from_collections(sample_collections, fields)

        assert len(contexts) == 3
        assert "Arctic Sea Ice" in contexts[0]
        assert "Global Temperature" in contexts[1]
        assert "Ocean Salinity" in contexts[2]

    def test_generate_contexts_from_empty_collections(self):
        """Test with empty collections list."""
        contexts = generate_contexts_from_collections([], ["title"])
        assert contexts == []

    def test_generate_answer_from_collections(self, sample_collections):
        """Test auto-generating answer from collections."""
        fields = ["title", "abstract"]

        answer = generate_answer_from_collections(sample_collections, fields)

        assert "Found 3 relevant data collections" in answer
        assert "Arctic Sea Ice Concentration Dataset" in answer

    def test_generate_answer_from_empty_collections(self):
        """Test answer generation with no collections."""
        answer = generate_answer_from_collections([], ["title"])
        assert "No relevant data collections were found" in answer


# === SingleEvaluation Class Tests ===


class TestSingleEvaluation:
    """Test SingleEvaluation class for per-request scoring."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset SingleEvaluation singleton before each test."""
        SingleEvaluation._llm = None
        SingleEvaluation._embeddings = None
        SingleEvaluation._relevance_prompt = None
        yield

    @patch("rag_eval.evals.create_bedrock_llm")
    @patch("rag_eval.evals.create_bedrock_embeddings")
    @patch("rag_eval.evals.DatasetRelevancePrompt")
    def test_initialize_components(self, mock_prompt, mock_embeddings, mock_llm):
        """Test component initialization (singleton pattern)."""
        mock_llm.return_value = MagicMock()
        mock_embeddings.return_value = MagicMock()
        mock_prompt.return_value = MagicMock()

        SingleEvaluation._initialize_components()

        assert SingleEvaluation._llm is not None
        assert SingleEvaluation._embeddings is not None
        assert SingleEvaluation._relevance_prompt is not None
        mock_llm.assert_called_once_with(
            model="amazon.nova-pro-v1:0", temperature=0.01, max_tokens=4096
        )

    @patch("rag_eval.evals.create_bedrock_llm")
    @patch("rag_eval.evals.create_bedrock_embeddings")
    @patch("rag_eval.evals.DatasetRelevancePrompt")
    def test_initialize_components_only_once(
        self, mock_prompt, mock_embeddings, mock_llm
    ):
        """Test that components are only initialized once (singleton)."""
        mock_llm.return_value = MagicMock()
        mock_embeddings.return_value = MagicMock()
        mock_prompt.return_value = MagicMock()

        SingleEvaluation._initialize_components()
        SingleEvaluation._initialize_components()

        mock_llm.assert_called_once()
        mock_embeddings.assert_called_once()
        mock_prompt.assert_called_once()

    @pytest.mark.asyncio
    @patch("rag_eval.evals.create_bedrock_llm")
    @patch("rag_eval.evals.create_bedrock_embeddings")
    @patch("rag_eval.evals.DatasetRelevancePrompt")
    async def test_compute_single_collection_relevance(
        self,
        mock_prompt_class,
        mock_embeddings,
        mock_llm,
        sample_collections,
        sample_question,
    ):
        """Test computing relevance for a single collection."""
        mock_llm.return_value = MagicMock()
        mock_embeddings.return_value = MagicMock()

        mock_result = MagicMock()
        mock_result.relevance_score = 0.8

        mock_prompt = AsyncMock()
        mock_prompt.generate.return_value = mock_result
        mock_prompt_class.return_value = mock_prompt

        score = await SingleEvaluation.compute_single_collection_relevance(
            question=sample_question, collection=sample_collections[0]
        )

        assert score == 0.8
        mock_prompt.generate.assert_called_once()

    @pytest.mark.asyncio
    @patch("rag_eval.evals.create_bedrock_llm")
    @patch("rag_eval.evals.create_bedrock_embeddings")
    @patch("rag_eval.evals.DatasetRelevancePrompt")
    async def test_compute_single_collection_relevance_with_retries(
        self,
        mock_prompt_class,
        mock_embeddings,
        mock_llm,
        sample_collections,
        sample_question,
    ):
        """Test retry logic on failures."""
        mock_llm.return_value = MagicMock()
        mock_embeddings.return_value = MagicMock()

        mock_prompt = AsyncMock()
        # Fail twice, succeed on third attempt
        mock_prompt.generate.side_effect = [
            Exception("Error 1"),
            Exception("Error 2"),
            MagicMock(relevance_score=0.7),
        ]
        mock_prompt_class.return_value = mock_prompt

        with patch("time.sleep"):  # Speed up test
            score = await SingleEvaluation.compute_single_collection_relevance(
                question=sample_question, collection=sample_collections[0]
            )

        assert score == 0.7
        assert mock_prompt.generate.call_count == 3

    @pytest.mark.asyncio
    @patch("rag_eval.evals.create_bedrock_llm")
    @patch("rag_eval.evals.create_bedrock_embeddings")
    @patch("rag_eval.evals.DatasetRelevancePrompt")
    async def test_compute_dataset_relevance_scores(
        self,
        mock_prompt_class,
        mock_embeddings,
        mock_llm,
        sample_collections,
        sample_question,
    ):
        """Test computing relevance scores for multiple collections."""
        mock_llm.return_value = MagicMock()
        mock_embeddings.return_value = MagicMock()

        mock_prompt = AsyncMock()
        mock_prompt.generate.side_effect = [
            MagicMock(relevance_score=0.9),
            MagicMock(relevance_score=0.7),
            MagicMock(relevance_score=0.5),
        ]
        mock_prompt_class.return_value = mock_prompt

        result = await SingleEvaluation.compute_dataset_relevance_scores(
            question=sample_question, collections=sample_collections
        )

        assert result["individual_scores"] == [0.9, 0.7, 0.5]
        assert abs(result["avg_relevance"] - 0.7) < 0.001  # Floating point comparison
        assert result["max_relevance"] == 0.9

    @pytest.mark.asyncio
    @patch("rag_eval.evals.create_bedrock_llm")
    @patch("rag_eval.evals.create_bedrock_embeddings")
    @patch("rag_eval.evals.DatasetRelevancePrompt")
    async def test_compute_dataset_relevance_empty_collections(
        self, mock_prompt_class, mock_embeddings, mock_llm, sample_question
    ):
        """Test with empty collections."""
        mock_llm.return_value = MagicMock()
        mock_embeddings.return_value = MagicMock()
        mock_prompt_class.return_value = AsyncMock()

        result = await SingleEvaluation.compute_dataset_relevance_scores(
            question=sample_question, collections=[]
        )

        assert result["individual_scores"] == []
        assert result["avg_relevance"] is None
        assert result["max_relevance"] is None

    @pytest.mark.asyncio
    @patch("rag_eval.evals.create_bedrock_llm")
    @patch("rag_eval.evals.create_bedrock_embeddings")
    @patch("rag_eval.evals.DatasetRelevancePrompt")
    @patch("rag_eval.evals.Faithfulness")
    async def test_compute_faithfulness(
        self,
        mock_faithfulness,
        mock_prompt_class,
        mock_embeddings,
        mock_llm,
        sample_question,
    ):
        """Test computing faithfulness score."""
        mock_llm_instance = MagicMock()
        mock_llm.return_value = mock_llm_instance
        mock_embeddings_instance = MagicMock()
        mock_embeddings.return_value = mock_embeddings_instance
        mock_prompt_class.return_value = AsyncMock()

        mock_metric = AsyncMock()
        mock_result = MagicMock()
        mock_result.value = 0.85
        mock_metric.ascore.return_value = mock_result
        mock_faithfulness.return_value = mock_metric

        score = await SingleEvaluation.compute_faithfulness(
            question=sample_question,
            contexts=["Context 1", "Context 2"],
            answer="Answer text",
        )

        assert score == 0.85
        mock_faithfulness.assert_called_once_with(
            llm=mock_llm_instance, embeddings=mock_embeddings_instance
        )
        mock_metric.ascore.assert_called_once()

    @pytest.mark.asyncio
    @patch("rag_eval.evals.create_bedrock_llm")
    @patch("rag_eval.evals.create_bedrock_embeddings")
    @patch("rag_eval.evals.DatasetRelevancePrompt")
    @patch("rag_eval.evals.AnswerRelevancy")
    async def test_compute_answer_relevancy(
        self,
        mock_answer_relevancy,
        mock_prompt_class,
        mock_embeddings,
        mock_llm,
        sample_question,
    ):
        """Test computing answer relevancy score."""
        mock_llm_instance = MagicMock()
        mock_llm.return_value = mock_llm_instance
        mock_embeddings_instance = MagicMock()
        mock_embeddings.return_value = mock_embeddings_instance
        mock_prompt_class.return_value = AsyncMock()

        mock_metric = AsyncMock()
        mock_result = MagicMock()
        mock_result.value = 0.9
        mock_metric.ascore.return_value = mock_result
        mock_answer_relevancy.return_value = mock_metric

        score = await SingleEvaluation.compute_answer_relevancy(
            question=sample_question, answer="Answer text"
        )

        assert score == 0.9
        mock_metric.ascore.assert_called_once()

    @pytest.mark.asyncio
    @patch("rag_eval.evals.create_bedrock_llm")
    @patch("rag_eval.evals.create_bedrock_embeddings")
    @patch("rag_eval.evals.DatasetRelevancePrompt")
    @patch("rag_eval.evals.ContextPrecision")
    async def test_compute_context_precision_with_reference(
        self,
        mock_context_precision,
        mock_prompt_class,
        mock_embeddings,
        mock_llm,
        sample_question,
    ):
        """Test computing context precision with reference."""
        mock_llm_instance = MagicMock()
        mock_llm.return_value = mock_llm_instance
        mock_embeddings.return_value = MagicMock()
        mock_prompt_class.return_value = AsyncMock()

        mock_metric = AsyncMock()
        mock_result = MagicMock()
        mock_result.value = 0.75
        mock_metric.ascore.return_value = mock_result
        mock_context_precision.return_value = mock_metric

        score = await SingleEvaluation.compute_context_precision_with_reference(
            question=sample_question,
            contexts=["Context 1"],
            reference="Ground truth",
        )

        assert score == 0.75
        mock_context_precision.assert_called_once_with(llm=mock_llm_instance)

    @pytest.mark.asyncio
    @patch("rag_eval.evals.create_bedrock_llm")
    @patch("rag_eval.evals.create_bedrock_embeddings")
    @patch("rag_eval.evals.DatasetRelevancePrompt")
    @patch("rag_eval.evals.ContextRecall")
    async def test_compute_context_recall(
        self,
        mock_context_recall,
        mock_prompt_class,
        mock_embeddings,
        mock_llm,
        sample_question,
    ):
        """Test computing context recall."""
        mock_llm_instance = MagicMock()
        mock_llm.return_value = mock_llm_instance
        mock_embeddings.return_value = MagicMock()
        mock_prompt_class.return_value = AsyncMock()

        mock_metric = AsyncMock()
        mock_result = MagicMock()
        mock_result.value = 0.8
        mock_metric.ascore.return_value = mock_result
        mock_context_recall.return_value = mock_metric

        score = await SingleEvaluation.compute_context_recall(
            question=sample_question,
            contexts=["Context 1"],
            reference="Ground truth",
        )

        assert score == 0.8
        mock_metric.ascore.assert_called_once()


# === EarthdataEvaluator Class Tests ===


class TestEarthdataEvaluator:
    """Test EarthdataEvaluator class."""

    def test_init(self):
        """Test evaluator initialization."""
        evaluator = EarthdataEvaluator(trace_name="test-trace")
        assert evaluator.trace_name == "test-trace"

    @patch.dict(os.environ, {}, clear=True)
    def test_init_default_trace_name(self):
        """Test default trace name."""
        evaluator = EarthdataEvaluator()
        assert evaluator.trace_name == "rag"

    def test_create_task_function(self):
        """Test task function creation."""
        evaluator = EarthdataEvaluator()
        task = evaluator.create_task_function()
        assert callable(task)

    @patch("rag_eval.evals.search_all_entity_types")
    @patch("rag_eval.evals.get_datastore")
    def test_embedding_task_execution(self, mock_get_datastore, mock_search):
        """Test embedding search task execution."""
        # Mock search results
        mock_search.return_value = [
            {
                "external_id": "C1234-POCLOUD",
                "type": "collection",
                "text_content": "Test content",
                "similarity": 0.9,
            }
        ]

        # Mock datastore
        mock_datastore = MagicMock()
        mock_datastore.fetch_collections_by_ids.return_value = {
            "C1234-POCLOUD": {
                "metadata": {
                    "EntryTitle": "Test Dataset",
                    "Abstract": "Test abstract",
                }
            }
        }
        mock_get_datastore.return_value = mock_datastore

        # Create mock item
        mock_item = MagicMock()
        mock_item.input = {"question": "Test question"}
        mock_item.expected_output = {"reference": "Test reference"}

        evaluator = EarthdataEvaluator()
        task = evaluator.create_task_function()
        result = task(item=mock_item)

        assert result["question"] == "Test question"
        assert result["reference"] == "Test reference"
        assert len(result["collections"]) == 1
        assert result["collections"][0]["concept_id"] == "C1234-POCLOUD"
        assert result["collections"][0]["title"] == "Test Dataset"

    def test_create_evaluators(self):
        """Test evaluator function creation."""
        evaluator = EarthdataEvaluator()
        evaluators = evaluator.create_evaluators()
        assert (
            len(evaluators) == 3
        )  # collection_relevance, context_precision, context_recall

    @pytest.mark.asyncio
    @patch("rag_eval.evals.SingleEvaluation.compute_dataset_relevance_scores")
    async def test_collection_relevance_evaluator(
        self, mock_compute, sample_collections
    ):
        """Test collection relevance evaluator."""
        mock_compute.return_value = {
            "individual_scores": [0.8, 0.6],
            "avg_relevance": 0.7,
            "max_relevance": 0.8,
        }

        evaluator = EarthdataEvaluator()
        evaluators = evaluator.create_evaluators()
        collection_relevance_eval = evaluators[0]

        output = {"question": "Test question", "collections": sample_collections[:2]}
        results = await collection_relevance_eval(output=output)

        assert len(results) == 2
        assert results[0].name == "embedding_collection_1_relevance"
        assert results[0].value == 0.8
        assert results[1].value == 0.6

    @pytest.mark.asyncio
    @patch("rag_eval.evals.SingleEvaluation.compute_context_precision_with_reference")
    async def test_context_precision_evaluator(self, mock_compute, sample_collections):
        """Test context precision evaluator."""
        mock_compute.return_value = 0.75

        evaluator = EarthdataEvaluator()
        evaluators = evaluator.create_evaluators()
        context_precision_eval = evaluators[1]

        output = {
            "question": "Test",
            "collections": sample_collections,
            "reference": "Ground truth",
        }
        result = await context_precision_eval(output=output)

        assert result.name == "embedding_context_precision"
        assert result.value == 0.75

    @pytest.mark.asyncio
    async def test_context_precision_evaluator_no_reference(self, sample_collections):
        """Test context precision evaluator without reference."""
        evaluator = EarthdataEvaluator()
        evaluators = evaluator.create_evaluators()
        context_precision_eval = evaluators[1]

        output = {
            "question": "Test",
            "collections": sample_collections,
            "reference": None,
        }
        result = await context_precision_eval(output=output)

        assert result is None

    @pytest.mark.asyncio
    @patch("rag_eval.evals.SingleEvaluation.compute_context_recall")
    async def test_context_recall_evaluator(self, mock_compute, sample_collections):
        """Test context recall evaluator."""
        mock_compute.return_value = 0.8

        evaluator = EarthdataEvaluator()
        evaluators = evaluator.create_evaluators()
        context_recall_eval = evaluators[2]

        output = {
            "question": "Test",
            "collections": sample_collections,
            "reference": "Ground truth",
        }
        result = await context_recall_eval(output=output)

        assert result.name == "embedding_context_recall"
        assert result.value == 0.8

    def test_create_run_evaluators(self):
        """Test run evaluator creation (should be empty)."""
        evaluator = EarthdataEvaluator()
        run_evaluators = evaluator.create_run_evaluators()
        assert run_evaluators == []

    @patch("rag_eval.evals.get_langfuse")
    @patch("rag_eval.evals.flush_langfuse")
    def test_run_experiment(self, mock_flush, mock_get_langfuse):
        """Test running an experiment."""
        mock_dataset = MagicMock()
        mock_dataset.items = [MagicMock()]
        mock_dataset.run_experiment.return_value = MagicMock()

        mock_langfuse = MagicMock()
        mock_langfuse.get_dataset.return_value = mock_dataset
        mock_get_langfuse.return_value = mock_langfuse

        evaluator = EarthdataEvaluator()
        result = evaluator.run_experiment(
            dataset_name="test-dataset", experiment_name="test-experiment"
        )

        assert result is not None
        mock_dataset.run_experiment.assert_called_once()
        mock_flush.assert_called_once()

    # === Main Function Tests ===

    @pytest.mark.asyncio
    @patch("rag_eval.evals.SingleEvaluation.compute_context_recall")
    async def test_context_recall_evaluator_no_reference(
        self, mock_compute, sample_collections
    ):
        """Test context recall evaluator without reference."""
        evaluator = EarthdataEvaluator()
        evaluators = evaluator.create_evaluators()
        context_recall_eval = evaluators[2]

        output = {
            "question": "Test",
            "collections": sample_collections,
            "reference": None,
        }
        result = await context_recall_eval(output=output)

        assert result is None
        mock_compute.assert_not_called()

    @pytest.mark.asyncio
    @patch("rag_eval.evals.SingleEvaluation.compute_context_recall")
    async def test_context_recall_evaluator_no_collections(self, mock_compute):
        """Test context recall evaluator without collections."""
        evaluator = EarthdataEvaluator()
        evaluators = evaluator.create_evaluators()
        context_recall_eval = evaluators[2]

        output = {"question": "Test", "collections": [], "reference": "Ground truth"}
        result = await context_recall_eval(output=output)

        assert result is None
        mock_compute.assert_not_called()

    @pytest.mark.asyncio
    async def test_collection_relevance_evaluator_empty_collections(self):
        """Test collection relevance evaluator with no collections."""
        evaluator = EarthdataEvaluator()
        evaluators = evaluator.create_evaluators()
        collection_relevance_eval = evaluators[0]

        output = {"question": "Test question", "collections": []}
        results = await collection_relevance_eval(output=output)

        assert results == []

    @pytest.mark.asyncio
    @patch("rag_eval.evals.SingleEvaluation.compute_dataset_relevance_scores")
    async def test_collection_relevance_evaluator_error_handling(
        self, mock_compute, sample_collections
    ):
        """Test error handling in collection relevance evaluator."""
        mock_compute.side_effect = Exception("Scoring error")

        evaluator = EarthdataEvaluator()
        evaluators = evaluator.create_evaluators()
        collection_relevance_eval = evaluators[0]

        output = {"question": "Test", "collections": sample_collections}
        results = await collection_relevance_eval(output=output)

        assert results == []

    @pytest.mark.asyncio
    @patch("rag_eval.evals.SingleEvaluation.compute_context_precision_with_reference")
    async def test_context_precision_evaluator_error_handling(
        self, mock_compute, sample_collections
    ):
        """Test error handling in context precision evaluator."""
        mock_compute.side_effect = Exception("Precision error")

        evaluator = EarthdataEvaluator()
        evaluators = evaluator.create_evaluators()
        context_precision_eval = evaluators[1]

        output = {
            "question": "Test",
            "collections": sample_collections,
            "reference": "ref",
        }
        result = await context_precision_eval(output=output)

        assert result is None

    @pytest.mark.asyncio
    @patch("rag_eval.evals.SingleEvaluation.compute_context_recall")
    async def test_context_recall_evaluator_error_handling(
        self, mock_compute, sample_collections
    ):
        """Test error handling in context recall evaluator."""
        mock_compute.side_effect = Exception("Recall error")

        evaluator = EarthdataEvaluator()
        evaluators = evaluator.create_evaluators()
        context_recall_eval = evaluators[2]

        output = {
            "question": "Test",
            "collections": sample_collections,
            "reference": "ref",
        }
        result = await context_recall_eval(output=output)

        assert result is None

    @pytest.mark.asyncio
    @patch("rag_eval.evals.SingleEvaluation.compute_context_precision_with_reference")
    async def test_context_precision_evaluator_returns_none_score(
        self, mock_compute, sample_collections
    ):
        """Test context precision evaluator when score is None."""
        mock_compute.return_value = None

        evaluator = EarthdataEvaluator()
        evaluators = evaluator.create_evaluators()
        context_precision_eval = evaluators[1]

        output = {
            "question": "Test",
            "collections": sample_collections,
            "reference": "ref",
        }
        result = await context_precision_eval(output=output)

        assert result is None

    @pytest.mark.asyncio
    @patch("rag_eval.evals.SingleEvaluation.compute_context_recall")
    async def test_context_recall_evaluator_returns_none_score(
        self, mock_compute, sample_collections
    ):
        """Test context recall evaluator when score is None."""
        mock_compute.return_value = None

        evaluator = EarthdataEvaluator()
        evaluators = evaluator.create_evaluators()
        context_recall_eval = evaluators[2]

        output = {
            "question": "Test",
            "collections": sample_collections,
            "reference": "ref",
        }
        result = await context_recall_eval(output=output)

        assert result is None

    @patch("rag_eval.evals.search_all_entity_types")
    @patch("rag_eval.evals.get_datastore")
    def test_embedding_task_execution_no_search_results(
        self, _mock_get_datastore, mock_search
    ):
        """Test embedding search task execution with no search results."""
        mock_search.return_value = []

        mock_item = MagicMock()
        mock_item.input = {"question": "Test question"}
        mock_item.expected_output = {}

        evaluator = EarthdataEvaluator()
        task = evaluator.create_task_function()
        result = task(item=mock_item)

        assert result["question"] == "Test question"
        assert result["collections"] == []
        assert (
            result["answer"]
            == "No relevant data collections found in embedding search."
        )

    @patch("rag_eval.evals.get_langfuse")
    @patch("rag_eval.evals.flush_langfuse")
    def test_run_experiment_with_custom_name(self, _mock_flush, mock_get_langfuse):
        """Test running an experiment with custom name."""
        mock_dataset = MagicMock()
        mock_dataset.items = []
        mock_dataset.run_experiment.return_value = MagicMock()

        mock_langfuse = MagicMock()
        mock_langfuse.get_dataset.return_value = mock_dataset
        mock_get_langfuse.return_value = mock_langfuse

        evaluator = EarthdataEvaluator()
        evaluator.run_experiment(
            dataset_name="test-dataset",
            experiment_name="custom-experiment",
            experiment_description="Test description",
            max_concurrency=5,
        )

        mock_dataset.run_experiment.assert_called_once()
        call_kwargs = mock_dataset.run_experiment.call_args.kwargs
        assert (
            "custom-experiment" in call_kwargs["name"]
        )  # 'name' parameter, not 'experiment_name'
        assert call_kwargs["max_concurrency"] == 5

    @patch("rag_eval.evals.get_langfuse")
    @patch("rag_eval.evals.flush_langfuse")
    def test_run_experiment_auto_generates_name(self, _mock_flush, mock_get_langfuse):
        """Test that experiment name is auto-generated when not provided."""
        mock_dataset = MagicMock()
        mock_dataset.items = []
        mock_dataset.run_experiment.return_value = MagicMock()

        mock_langfuse = MagicMock()
        mock_langfuse.get_dataset.return_value = mock_dataset
        mock_get_langfuse.return_value = mock_langfuse

        evaluator = EarthdataEvaluator(trace_name="test-trace")
        evaluator.run_experiment(
            dataset_name="test-dataset",
            experiment_name=None,  # No experiment name provided
        )

        mock_dataset.run_experiment.assert_called_once()
        call_kwargs = mock_dataset.run_experiment.call_args.kwargs
        # Should auto-generate: {trace_name}_embedding_eval_{dataset_name}
        assert "test-trace_embedding_eval_test-dataset" in call_kwargs["name"]


# === SingleEvaluation Error Handling Tests ===


class TestSingleEvaluationErrorHandling:
    """Test error handling in SingleEvaluation compute methods."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset SingleEvaluation singleton before each test."""
        SingleEvaluation._llm = None
        SingleEvaluation._embeddings = None
        SingleEvaluation._relevance_prompt = None
        yield

    @pytest.mark.asyncio
    @patch("rag_eval.evals.create_bedrock_llm")
    @patch("rag_eval.evals.create_bedrock_embeddings")
    @patch("rag_eval.evals.DatasetRelevancePrompt")
    async def test_compute_single_collection_relevance_max_retries_exceeded(
        self,
        mock_prompt_class,
        mock_embeddings,
        mock_llm,
        sample_collections,
        sample_question,
    ):
        """Test collection relevance when all retries fail."""
        mock_llm.return_value = MagicMock()
        mock_embeddings.return_value = MagicMock()

        mock_prompt = AsyncMock()
        mock_prompt.generate.side_effect = Exception("Persistent error")
        mock_prompt_class.return_value = mock_prompt

        with patch("time.sleep"):
            score = await SingleEvaluation.compute_single_collection_relevance(
                question=sample_question, collection=sample_collections[0]
            )

        assert score is None
        assert mock_prompt.generate.call_count == 3

    @pytest.mark.asyncio
    @patch("rag_eval.evals.create_bedrock_llm")
    @patch("rag_eval.evals.create_bedrock_embeddings")
    @patch("rag_eval.evals.DatasetRelevancePrompt")
    async def test_compute_single_collection_relevance_outer_exception(
        self, mock_prompt_class, mock_embeddings, mock_llm, sample_question
    ):
        """Test outer exception handler when collection field extraction fails."""
        mock_llm.return_value = MagicMock()
        mock_embeddings.return_value = MagicMock()
        mock_prompt = AsyncMock()
        mock_prompt_class.return_value = mock_prompt

        SingleEvaluation._initialize_components()

        # Create a collection-like object that raises an error during dict comprehension
        bad_collection = {"concept_id": "C1234", "title": "Test"}

        # Patch the DatasetRelevanceInput to raise an exception during creation
        with patch(
            "rag_eval.evals.DatasetRelevanceInput", side_effect=TypeError("Field error")
        ):
            score = await SingleEvaluation.compute_single_collection_relevance(
                question=sample_question, collection=bad_collection
            )

        assert score is None

    @pytest.mark.asyncio
    @patch("rag_eval.evals.create_bedrock_llm")
    @patch("rag_eval.evals.create_bedrock_embeddings")
    @patch("rag_eval.evals.DatasetRelevancePrompt")
    @patch("rag_eval.evals.Faithfulness")
    async def test_compute_faithfulness_error(
        self,
        mock_faithfulness,
        mock_prompt_class,
        mock_embeddings,
        mock_llm,
        sample_question,
    ):
        """Test error handling in faithfulness computation."""
        mock_llm.return_value = MagicMock()
        mock_embeddings.return_value = MagicMock()
        mock_prompt_class.return_value = AsyncMock()

        mock_metric = AsyncMock()
        mock_metric.ascore.side_effect = Exception("Faithfulness error")
        mock_faithfulness.return_value = mock_metric

        score = await SingleEvaluation.compute_faithfulness(
            question=sample_question, contexts=["Context"], answer="Answer"
        )

        assert score is None

    @pytest.mark.asyncio
    @patch("rag_eval.evals.create_bedrock_llm")
    @patch("rag_eval.evals.create_bedrock_embeddings")
    @patch("rag_eval.evals.DatasetRelevancePrompt")
    @patch("rag_eval.evals.AnswerRelevancy")
    async def test_compute_answer_relevancy_error(
        self,
        mock_answer_relevancy,
        mock_prompt_class,
        mock_embeddings,
        mock_llm,
        sample_question,
    ):
        """Test error handling in answer relevancy computation."""
        mock_llm.return_value = MagicMock()
        mock_embeddings.return_value = MagicMock()
        mock_prompt_class.return_value = AsyncMock()

        mock_metric = AsyncMock()
        mock_metric.ascore.side_effect = Exception("Relevancy error")
        mock_answer_relevancy.return_value = mock_metric

        score = await SingleEvaluation.compute_answer_relevancy(
            question=sample_question, answer="Answer"
        )

        assert score is None

    @pytest.mark.asyncio
    @patch("rag_eval.evals.create_bedrock_llm")
    @patch("rag_eval.evals.create_bedrock_embeddings")
    @patch("rag_eval.evals.DatasetRelevancePrompt")
    @patch("rag_eval.evals.ContextPrecision")
    async def test_compute_context_precision_error(
        self,
        mock_context_precision,
        mock_prompt_class,
        mock_embeddings,
        mock_llm,
        sample_question,
    ):
        """Test error handling in context precision computation."""
        mock_llm.return_value = MagicMock()
        mock_embeddings.return_value = MagicMock()
        mock_prompt_class.return_value = AsyncMock()

        mock_metric = AsyncMock()
        mock_metric.ascore.side_effect = Exception("Precision error")
        mock_context_precision.return_value = mock_metric

        score = await SingleEvaluation.compute_context_precision_with_reference(
            question=sample_question, contexts=["Context"], reference="ref"
        )

        assert score is None

    @pytest.mark.asyncio
    @patch("rag_eval.evals.create_bedrock_llm")
    @patch("rag_eval.evals.create_bedrock_embeddings")
    @patch("rag_eval.evals.DatasetRelevancePrompt")
    @patch("rag_eval.evals.ContextRecall")
    async def test_compute_context_recall_error(
        self,
        mock_context_recall,
        mock_prompt_class,
        mock_embeddings,
        mock_llm,
        sample_question,
    ):
        """Test error handling in context recall computation."""
        mock_llm.return_value = MagicMock()
        mock_embeddings.return_value = MagicMock()
        mock_prompt_class.return_value = AsyncMock()

        mock_metric = AsyncMock()
        mock_metric.ascore.side_effect = Exception("Recall error")
        mock_context_recall.return_value = mock_metric

        score = await SingleEvaluation.compute_context_recall(
            question=sample_question, contexts=["Context"], reference="ref"
        )

        assert score is None


# === Main Function Tests ===


class TestMainFunction:
    """Test main() entry point."""

    @patch("rag_eval.evals.EarthdataEvaluator")
    @patch.dict(os.environ, {"DATASET_NAME": "test-dataset"})
    def test_main_success(self, mock_evaluator_class):
        """Test successful main() execution."""
        from rag_eval.evals import main

        mock_evaluator = MagicMock()
        mock_evaluator_class.return_value = mock_evaluator

        main()

        mock_evaluator_class.assert_called_once()
        mock_evaluator.run_experiment.assert_called_once_with(
            dataset_name="test-dataset", experiment_name=None, max_concurrency=3
        )

    @patch.dict(os.environ, {}, clear=True)
    def test_main_missing_dataset_name(self):
        """Test main() raises error when DATASET_NAME is missing."""
        from rag_eval.evals import main

        with pytest.raises(ValueError, match="DATASET_NAME environment variable"):
            main()

    @patch("util.rag_eval.ragas_utils.llm_factory")
    def test_create_bedrock_llm_default_params(self, mock_llm_factory):
        """Test creating LLM with default parameters."""
        from util.rag_eval.ragas_utils import create_bedrock_llm

        mock_llm_factory.return_value = MagicMock()

        create_bedrock_llm()

        mock_llm_factory.assert_called_once()
        call_args = mock_llm_factory.call_args
        assert call_args[0][0] == "bedrock/amazon.nova-pro-v1:0"
        assert call_args[1]["temperature"] == 0.01
        assert call_args[1]["max_tokens"] == 10000

    @patch("util.rag_eval.ragas_utils.llm_factory")
    def test_create_bedrock_llm_custom_params(self, mock_llm_factory):
        """Test creating LLM with custom parameters."""
        from util.rag_eval.ragas_utils import create_bedrock_llm

        mock_llm_factory.return_value = MagicMock()

        create_bedrock_llm(
            model="amazon.nova-lite-v1:0", temperature=0.5, max_tokens=2000
        )

        mock_llm_factory.assert_called_once()
        call_args = mock_llm_factory.call_args
        assert call_args[0][0] == "bedrock/amazon.nova-lite-v1:0"
        assert call_args[1]["temperature"] == 0.5
        assert call_args[1]["max_tokens"] == 2000

    @patch("util.rag_eval.ragas_utils.embedding_factory")
    def test_create_bedrock_embeddings_default(self, mock_embedding_factory):
        """Test creating embeddings with default model."""
        from util.rag_eval.ragas_utils import create_bedrock_embeddings

        mock_embedding_factory.return_value = MagicMock()

        create_bedrock_embeddings()

        mock_embedding_factory.assert_called_once_with(
            "litellm", model="bedrock/amazon.titan-embed-text-v2:0"
        )

    @patch("util.rag_eval.ragas_utils.embedding_factory")
    def test_create_bedrock_embeddings_custom_model(self, mock_embedding_factory):
        """Test creating embeddings with custom model."""
        from util.rag_eval.ragas_utils import create_bedrock_embeddings

        mock_embedding_factory.return_value = MagicMock()

        create_bedrock_embeddings(model="cohere.embed-english-v3")

        mock_embedding_factory.assert_called_once_with(
            "litellm", model="bedrock/cohere.embed-english-v3"
        )
