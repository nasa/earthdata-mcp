"""Offline RAG evaluation for Earthdata MCP server."""

import asyncio
import json
import logging
import os
from pathlib import Path

import nest_asyncio
from dotenv import load_dotenv
from ragas import Dataset
from ragas.metrics import (
    Faithfulness,
    LLMContextPrecisionWithoutReference,
)

from langfuse import Evaluation
from rag_eval.mcp_client import EarthdataRAGClient
from rag_eval.models import DatasetRelevanceInput, DatasetRelevancePrompt
from rag_eval.ragas_utils import (
    create_bedrock_llm,
    create_bedrock_embeddings,
    init_ragas_metrics,
    score_with_ragas,
)
from util.langfuse import get_langfuse, flush_langfuse

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file (override existing ones)
load_dotenv(override=True)

# Apply nest_asyncio to allow nested event loops (for PydanticPrompt.generate in evaluators)
nest_asyncio.apply()


# === Evaluation Utility Functions ===


def format_collection_context(
    collection: dict,
    fields: list[str],
) -> str:
    """
    Format a single collection into a context string.

    Args:
        collection: Collection dictionary
        fields: Fields to extract from the collection

    Returns:
        Formatted context string with "Field Name: value" format
    """
    parts = []
    for field in fields:
        value = collection.get(field)
        if value:
            field_label = field.replace("_", " ").title()
            parts.append(f"{field_label}: {value}")
    return "\n".join(parts)


def generate_contexts_from_collections(
    collections: list[dict],
    fields: list[str],
) -> list[str]:
    """
    Generate context strings from a list of collections.

    Args:
        collections: List of collection dictionaries
        fields: Fields to extract from each collection

    Returns:
        List of formatted context strings
    """
    return [format_collection_context(c, fields) for c in collections]


def generate_answer_from_collections(
    collections: list[dict],
    fields: list[str],
) -> str:
    """
    Generate a simple answer from collections.

    WARNING: For evaluation purposes, you should use the actual system-generated
    answer, not this auto-generated one. Using this creates circularity where
    contexts and answer are derived from the same source, artificially inflating
    metrics like Faithfulness.

    This function is only useful for:
    - Testing/debugging
    - Cases where you only have collections but no generated answer

    Args:
        collections: List of collection dictionaries
        fields: Fields used (first field assumed to be the primary identifier)

    Returns:
        Simple answer string
    """
    if not collections:
        return "No relevant data collections were found for your query."

    # Use first field as primary identifier (usually title)
    primary_field = fields[0] if fields else next(iter(collections[0].keys()), "id")
    top_identifiers = ", ".join(
        str(c.get(primary_field, "Unknown")) for c in collections[:3]
    )
    return (
        f"Found {len(collections)} relevant data collections. "
        f"Top matches include: {top_identifiers}."
    )


# === Evaluation Classes ===


class EarthdataEvaluator:
    """Evaluator for Earthdata RAG system using Ragas metrics and Langfuse experiments"""

    def __init__(
        self,
        mcp_server_url: str,
        llm_model: str = "amazon.nova-pro-v1:0",
        temperature: float = 0.01,
        trace_name: str = "rag",
    ):
        """
        Initialize the evaluator.

        Args:
            mcp_server_url: URL of the MCP server to evaluate
            llm_model: Bedrock LLM model for evaluation scoring
            temperature: LLM temperature
            trace_name: Name for Langfuse traces
        """
        # Set up RAG client
        self.rag_client = EarthdataRAGClient(server_url=mcp_server_url)
        self.trace_name = trace_name

    def create_task_function(self):
        """
        Create task function for run_experiment.

        The task function is what Langfuse calls for EACH dataset item.
        It's the "system under test" - it runs your RAG pipeline on a question
        and returns the output that evaluators will score.

        Returns:
            Task function that queries the MCP server
        """

        def task(*, item, **kwargs):
            """
            Task function - this is YOUR SYSTEM that gets evaluated.

            Langfuse calls this once per dataset item (question).

            Flow:
            1. Extract question from dataset item
            2. Query MCP server (your RAG system)
            3. Return results for evaluators to score

            Args:
                item: DatasetItemClient with input={"question": "..."}
                **kwargs: Additional Langfuse context

            Returns:
                dict with answer, collections, question
                (evaluators receive this as 'output' parameter)
            """
            # Extract question from dataset item
            question = item.input.get("question")

            # Query MCP server
            response = self.rag_client.query(question)

            # Extract collections and answer
            collections = []
            if "raw_result" in response:
                collections = response["raw_result"].get("collections", [])

            answer = response.get("answer", "")

            # Return output with both answer and collections for evaluators
            return {
                "answer": answer,
                "collections": collections,
                "question": question,
            }

        return task

    def create_evaluators(self):
        """
        Create evaluator functions for run_experiment.

        Returns:
            List of evaluator functions
        """
        evaluators = []

        # Evaluator for average dataset relevance
        def avg_dataset_relevance_evaluator(*, output, **kwargs):
            """Evaluate average dataset relevance."""
            try:
                question = output.get("question", "")
                collections = output.get("collections", [])

                logger.info(
                    f"Computing avg relevance for {len(collections)} collections"
                )

                scores = SingleEvaluation.compute_dataset_relevance_scores(
                    question=question,
                    collections=collections,
                )

                avg_value = scores.get("avg_relevance")
                logger.info(f"Avg relevance computed: {avg_value}")

                if avg_value is None:
                    logger.warning("avg_relevance is None, skipping evaluation")
                    return None

                return Evaluation(
                    name="avg_dataset_relevance",
                    value=avg_value,
                    comment=f"Average relevance: {avg_value:.3f}",
                )
            except Exception as e:
                logger.error(
                    f"Error in avg_dataset_relevance_evaluator: {e}", exc_info=True
                )
                return None

        # Evaluator for max dataset relevance
        def max_dataset_relevance_evaluator(*, output, **kwargs):
            """Evaluate max dataset relevance."""
            try:
                question = output.get("question", "")
                collections = output.get("collections", [])

                logger.info(
                    f"Computing max relevance for {len(collections)} collections"
                )

                scores = SingleEvaluation.compute_dataset_relevance_scores(
                    question=question,
                    collections=collections,
                )

                max_value = scores.get("max_relevance")
                logger.info(f"Max relevance computed: {max_value}")

                if max_value is None:
                    logger.warning("max_relevance is None, skipping evaluation")
                    return None

                return Evaluation(
                    name="max_dataset_relevance",
                    value=max_value,
                    comment=f"Max relevance: {max_value:.3f}",
                )
            except Exception as e:
                logger.error(
                    f"Error in max_dataset_relevance_evaluator: {e}", exc_info=True
                )
                return None

        # Evaluator for faithfulness (Ragas)
        def faithfulness_evaluator(*, output, **kwargs):
            """Evaluate faithfulness using Ragas."""
            try:
                question = output.get("question", "")
                collections = output.get("collections", [])
                answer = output.get("answer", "")

                logger.info(f"Computing faithfulness for answer: {answer[:100]}...")

                # Generate contexts from collections
                contexts = generate_contexts_from_collections(
                    collections,
                    fields=["title", "abstract"],
                )

                logger.info(f"Generated {len(contexts)} contexts")

                score = SingleEvaluation.compute_faithfulness(
                    question=question,
                    contexts=contexts,
                    answer=answer,
                )

                logger.info(f"Faithfulness score computed: {score}")

                if score is None:
                    logger.warning("Faithfulness score is None, skipping evaluation")
                    return None

                return Evaluation(
                    name="faithfulness",
                    value=score,
                    comment=f"Faithfulness: {score:.3f}",
                )
            except Exception as e:
                logger.error(f"Error in faithfulness_evaluator: {e}", exc_info=True)
                return None

        # Evaluator for context precision (Ragas)
        def context_precision_evaluator(*, output, **kwargs):
            """Evaluate context precision using Ragas."""
            try:
                question = output.get("question", "")
                collections = output.get("collections", [])
                answer = output.get("answer", "")

                logger.info(
                    f"Computing context precision for {len(collections)} collections"
                )

                # Generate contexts from collections
                contexts = generate_contexts_from_collections(
                    collections,
                    fields=["title", "abstract"],
                )

                logger.info(f"Generated {len(contexts)} contexts")

                score = SingleEvaluation.compute_context_precision(
                    question=question,
                    contexts=contexts,
                    answer=answer,
                )

                logger.info(f"Context precision score computed: {score}")

                if score is None:
                    logger.warning(
                        "Context precision score is None, skipping evaluation"
                    )
                    return None

                return Evaluation(
                    name="context_precision",
                    value=score,
                    comment=f"Context precision: {score:.3f}",
                )
            except Exception as e:
                logger.error(
                    f"Error in context_precision_evaluator: {e}", exc_info=True
                )
                return None

        # Evaluator for number of datasets returned
        def num_datasets_evaluator(*, output, **kwargs):
            """Track number of datasets returned."""
            collections = output.get("collections", [])
            return Evaluation(
                name="num_datasets_returned",
                value=len(collections),
                comment=f"Returned {len(collections)} collections",
            )

        evaluators.extend(
            [
                avg_dataset_relevance_evaluator,
                max_dataset_relevance_evaluator,
                faithfulness_evaluator,
                context_precision_evaluator,
                num_datasets_evaluator,
            ]
        )

        return evaluators

    def create_run_evaluators(self):
        """
        Create run-level evaluator functions for aggregate metrics.

        DIFFERENCE FROM create_evaluators:
        - Item-level evaluators (create_evaluators): Run on EACH test case
          → "What's the faithfulness of question 1? question 2? etc."
        - Run-level evaluators (create_run_evaluators): Aggregate across ALL test cases
          → "What's the AVERAGE faithfulness across the entire experiment?"

        These run AFTER all item-level evaluations are complete.

        Returns:
            List of run-level evaluator functions
        """
        run_evaluators = []

        # Run-level: Average of average dataset relevance
        def run_avg_dataset_relevance(*, item_results, **kwargs):
            """Calculate average dataset relevance across all test cases."""
            scores = [
                eval.value
                for result in item_results
                for eval in result.evaluations
                if eval.name == "avg_dataset_relevance" and eval.value is not None
            ]

            if not scores:
                logger.warning(
                    "No avg_dataset_relevance scores to aggregate, skipping run-level evaluator"
                )
                return None  # Don't create an Evaluation with None value

            avg = sum(scores) / len(scores)
            return Evaluation(
                name="run_avg_dataset_relevance",
                value=avg,
                comment=f"Average dataset relevance across {len(scores)} test cases: {avg:.3f}",
            )

        # Run-level: Average faithfulness
        def run_avg_faithfulness(*, item_results, **kwargs):
            """Calculate average faithfulness across all test cases."""
            scores = [
                eval.value
                for result in item_results
                for eval in result.evaluations
                if eval.name == "faithfulness" and eval.value is not None
            ]

            if not scores:
                logger.warning(
                    "No faithfulness scores to aggregate, skipping run-level evaluator"
                )
                return None

            avg = sum(scores) / len(scores)
            return Evaluation(
                name="run_avg_faithfulness",
                value=avg,
                comment=f"Average faithfulness across {len(scores)} test cases: {avg:.3f}",
            )

        # Run-level: Average context precision
        def run_avg_context_precision(*, item_results, **kwargs):
            """Calculate average context precision across all test cases."""
            scores = [
                eval.value
                for result in item_results
                for eval in result.evaluations
                if eval.name == "context_precision" and eval.value is not None
            ]

            if not scores:
                logger.warning(
                    "No context_precision scores to aggregate, skipping run-level evaluator"
                )
                return None

            avg = sum(scores) / len(scores)
            return Evaluation(
                name="run_avg_context_precision",
                value=avg,
                comment=f"Average context precision across {len(scores)} test cases: {avg:.3f}",
            )

        # Run-level: Average number of datasets
        def run_avg_num_datasets(*, item_results, **kwargs):
            """Calculate average number of datasets returned."""
            counts = [
                eval.value
                for result in item_results
                for eval in result.evaluations
                if eval.name == "num_datasets_returned" and eval.value is not None
            ]

            if not counts:
                logger.warning(
                    "No num_datasets_returned scores to aggregate, skipping run-level evaluator"
                )
                return None

            avg = sum(counts) / len(counts)
            return Evaluation(
                name="run_avg_num_datasets",
                value=avg,
                comment=f"Average datasets returned: {avg:.1f}",
            )

        run_evaluators.extend(
            [
                run_avg_dataset_relevance,
                run_avg_faithfulness,
                run_avg_context_precision,
                run_avg_num_datasets,
            ]
        )

        return run_evaluators

    def run_experiment(
        self,
        dataset_name: str,
        experiment_name: str | None = None,
        experiment_description: str | None = None,
        max_concurrency: int = 3,
    ):
        """
        Run experiment on a Langfuse dataset using run_experiment.

        Args:
            dataset_name: Name of the Langfuse dataset
            experiment_name: Name for this experiment run
            experiment_description: Description for this experiment
            max_concurrency: Maximum concurrent task executions

        Returns:
            Experiment result object
        """
        langfuse = get_langfuse()

        # Load dataset from Langfuse
        logger.info(f"Loading dataset: {dataset_name}")
        dataset = langfuse.get_dataset(dataset_name)

        # Create task and evaluators
        task = self.create_task_function()
        evaluators = self.create_evaluators()
        run_evaluators = self.create_run_evaluators()

        # Set default experiment name if not provided
        if not experiment_name:
            experiment_name = f"{dataset_name}_evaluation"

        # Run experiment
        logger.info(f"Running experiment: {experiment_name}")
        logger.info(f"Dataset: {dataset_name} ({len(dataset.items)} items)")
        logger.info(
            f"Evaluators: {len(evaluators)} item-level, {len(run_evaluators)} run-level"
        )

        result = dataset.run_experiment(
            name=experiment_name,
            description=experiment_description or f"Evaluation of {dataset_name}",
            task=task,
            evaluators=evaluators,
            run_evaluators=run_evaluators,
            max_concurrency=max_concurrency,
        )

        # Print results
        logger.info("=" * 70)
        logger.info("Experiment Results:")
        logger.info("=" * 70)
        print(result.format())

        # Flush to ensure all data is sent
        flush_langfuse()

        return result

    def close(self):
        """Close the RAG client connection"""
        if hasattr(self, "rag_client"):
            self.rag_client.close()


class SingleEvaluation:
    """
    Single-instance evaluator for scoring one query/response pair.

    This is the core evaluation logic that both offline batch evaluation
    and online per-request evaluation use.
    """

    # Singleton class variables
    _llm = None
    _embeddings = None
    _relevance_prompt = None
    _metrics = None

    @classmethod
    def _initialize_components(cls):
        """Initialize evaluation components once (singleton pattern)."""
        if cls._llm is None:
            cls._llm = create_bedrock_llm(
                model="amazon.nova-pro-v1:0",
                temperature=0.01,
                max_tokens=4096,
            )
            cls._embeddings = create_bedrock_embeddings()
            cls._relevance_prompt = DatasetRelevancePrompt()

            # Initialize Ragas metrics
            cls._metrics = [
                Faithfulness(),
                LLMContextPrecisionWithoutReference(),
            ]
            init_ragas_metrics(cls._metrics, cls._llm, cls._embeddings)

    @classmethod
    def compute_dataset_relevance_scores(
        cls,
        question: str,
        collections: list[dict],
        collection_fields: list[str] | None = None,
    ) -> dict:
        """
        Compute dataset relevance scores for individual collections.

        Args:
            question: User query
            collections: List of collection dicts
            collection_fields: Fields to extract from collections (default: ["title", "abstract"])

        Returns:
            dict with individual_scores, avg_relevance, max_relevance
        """
        cls._initialize_components()

        # Default collection fields
        if collection_fields is None:
            collection_fields = ["title", "abstract"]

        # Score individual collections using relevance prompt
        collection_scores = []
        for collection in collections:
            try:
                # Extract only the specified fields for relevance scoring
                dataset_subset = {
                    field: collection.get(field, "") for field in collection_fields
                }

                prompt_input = DatasetRelevanceInput(
                    question=question,
                    dataset=dataset_subset,
                )
                # PydanticPrompt.generate() is async - asyncio.run() works with nest_asyncio
                result = asyncio.run(
                    cls._relevance_prompt.generate(data=prompt_input, llm=cls._llm)
                )
                collection_scores.append(result.relevance_score)
            except Exception as e:
                logger.warning(f"Error scoring collection: {e}")
                continue

        # Compute aggregates
        result = {
            "individual_scores": collection_scores,
            "avg_relevance": None,
            "max_relevance": None,
        }

        if collection_scores:
            result["avg_relevance"] = sum(collection_scores) / len(collection_scores)
            result["max_relevance"] = max(collection_scores)

        return result

    @classmethod
    def compute_faithfulness(
        cls,
        question: str,
        contexts: list[str],
        answer: str,
    ) -> float | None:
        """
        Compute faithfulness score using Ragas.

        Args:
            question: User query
            contexts: Retrieved contexts
            answer: Generated answer

        Returns:
            Faithfulness score (0-1) or None if error
        """
        cls._initialize_components()

        try:
            # Use the first metric which is Faithfulness
            faithfulness_metric = cls._metrics[0]
            ragas_scores = score_with_ragas(
                [faithfulness_metric],
                question,
                contexts,
                answer,
            )
            return ragas_scores.get("faithfulness")
        except Exception as e:
            logger.warning(f"Error computing faithfulness: {e}")
            return None

    @classmethod
    def compute_context_precision(
        cls,
        question: str,
        contexts: list[str],
        answer: str,
    ) -> float | None:
        """
        Compute context precision score using Ragas.

        Args:
            question: User query
            contexts: Retrieved contexts
            answer: Generated answer

        Returns:
            Context precision score (0-1) or None if error
        """
        cls._initialize_components()

        try:
            # Use the second metric which is LLMContextPrecisionWithoutReference
            context_precision_metric = cls._metrics[1]
            ragas_scores = score_with_ragas(
                [context_precision_metric],
                question,
                contexts,
                answer,
            )
            return ragas_scores.get("context_precision")
        except Exception as e:
            logger.warning(f"Error computing context precision: {e}")
            return None

    @classmethod
    def evaluate_single(
        cls,
        question: str,
        collections: list[dict],
        contexts: list[str] | None = None,
        answer: str | None = None,
        collection_fields: list[str] | None = None,
    ) -> dict[str, float]:
        """
        Evaluate a single query/response and return all scores.

        This is the core evaluation that both batch and online evaluation use.
        The caller is responsible for sending scores to Langfuse.

        Args:
            question: User query
            collections: List of collection dicts
            contexts: Retrieved contexts (auto-generated from collections if not provided)
            answer: Generated answer (SHOULD be actual system output; auto-generated only for testing)
            collection_fields: Fields to extract from collections (default: ["title", "abstract"])
                              First field is used as primary identifier, second for detailed description

        Returns:
            Dictionary of all scores with metadata: {"metric_name": {"value": X, "comment": "...", "data_type": "NUMERIC"}}
        """
        cls._initialize_components()
        all_scores = {}

        # Default collection fields
        if collection_fields is None:
            collection_fields = ["title", "abstract"]

        # Auto-generate contexts if not provided
        if contexts is None:
            contexts = generate_contexts_from_collections(
                collections, collection_fields
            )

        # Auto-generate answer if not provided
        # WARNING: This creates circularity - only use for testing!
        if answer is None:
            logger.warning(
                "Auto-generating answer from collections. "
                "For real evaluation, provide the actual system-generated answer "
                "to avoid circular evaluation (answer derived from same contexts)."
            )
            answer = generate_answer_from_collections(collections, collection_fields)

        # Define metrics metadata - makes it easy to add/remove metrics
        # Each metric has: name, compute function, comment, data type, result keys
        metrics_metadata = [
            {
                "name": "dataset_relevance",
                "compute": lambda: cls.compute_dataset_relevance_scores(
                    question=question,
                    collections=collections,
                    collection_fields=collection_fields,
                ),
                "results": [
                    {
                        "key": "individual_scores",
                        "score_name": "individual_dataset_scores",
                        "comment": "Individual relevance scores for each dataset",
                        "data_type": "LIST",
                    },
                    {
                        "key": "avg_relevance",
                        "score_name": "avg_dataset_relevance",
                        "comment": "Average relevance of individual datasets",
                        "data_type": "NUMERIC",
                    },
                    {
                        "key": "max_relevance",
                        "score_name": "max_dataset_relevance",
                        "comment": "Best dataset relevance score",
                        "data_type": "NUMERIC",
                    },
                ],
            },
            {
                "name": "faithfulness",
                "compute": lambda: cls.compute_faithfulness(
                    question=question,
                    contexts=contexts,
                    answer=answer,
                ),
                "results": [
                    {
                        "key": None,  # Direct scalar result
                        "score_name": "faithfulness",
                        "comment": "Ragas faithfulness metric",
                        "data_type": "NUMERIC",
                    },
                ],
            },
            {
                "name": "context_precision",
                "compute": lambda: cls.compute_context_precision(
                    question=question,
                    contexts=contexts,
                    answer=answer,
                ),
                "results": [
                    {
                        "key": None,  # Direct scalar result
                        "score_name": "context_precision",
                        "comment": "Ragas context_precision metric",
                        "data_type": "NUMERIC",
                    },
                ],
            },
        ]

        # Compute all metrics dynamically
        for metric_meta in metrics_metadata:
            try:
                result = metric_meta["compute"]()

                # Process each result defined in metadata
                for result_spec in metric_meta["results"]:
                    if result_spec["key"] is None:
                        # Direct scalar result
                        value = result
                    else:
                        # Dict result - extract specific key
                        value = (
                            result.get(result_spec["key"])
                            if isinstance(result, dict)
                            else None
                        )

                    # Only add if value is not None
                    if value is not None:
                        all_scores[result_spec["score_name"]] = {
                            "value": value,
                            "comment": result_spec["comment"],
                            "data_type": result_spec["data_type"],
                        }
            except Exception as e:
                logger.warning(f"Error computing {metric_meta['name']}: {e}")

        return all_scores


def main():
    """Main entry point for running evaluations."""
    # Get configuration from environment
    mcp_server_url = os.getenv(
        "MCP_SERVER_URL", "https://cmr.sit.earthdata.nasa.gov/mcp"
    )
    dataset_name = os.getenv("DATASET_NAME")
    experiment_name = os.getenv("EXPERIMENT_NAME")
    max_concurrency = int(os.getenv("MAX_CONCURRENCY", "3"))

    if not dataset_name:
        raise ValueError(
            "DATASET_NAME environment variable not set. "
            "Example: earthdata/manual-test"
        )

    # Initialize evaluator
    evaluator = EarthdataEvaluator(
        mcp_server_url=mcp_server_url,
    )

    try:
        # Run experiment using run_experiment API
        result = evaluator.run_experiment(
            dataset_name=dataset_name,
            experiment_name=experiment_name,
            max_concurrency=max_concurrency,
        )

        logger.info("=" * 70)
        logger.info("Evaluation complete!")
        logger.info(f"View results in Langfuse UI: {os.getenv('LANGFUSE_BASE_URL')}")

    finally:
        # Clean up resources
        evaluator.close()


if __name__ == "__main__":
    main()
