"""Offline RAG evaluation for Earthdata MCP server."""

import logging
import os
from datetime import datetime

import nest_asyncio
from langfuse import Evaluation
from ragas.metrics.collections import (
    AnswerRelevancy,
    ContextPrecision,
    ContextRecall,
    Faithfulness,
)
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from models.rag_eval import DatasetRelevanceInput, DatasetRelevancePrompt
from tools.discover_data.utils.embedding_search import search_all_entity_types
from util.datastores import get_datastore
from util.langfuse import flush_langfuse, get_langfuse
from util.rag_eval.collection_formatting import generate_contexts_from_collections
from util.rag_eval.ragas_utils import (
    create_bedrock_embeddings,
    create_bedrock_llm,
)

logger = logging.getLogger(__name__)


# === Evaluation Classes ===


class EarthdataEvaluator:
    """
    Evaluator for Earthdata RAG system using Langfuse experiments SDK.

    Implements the Langfuse experiment pattern:
    1. Task function: Runs your RAG system on each dataset item
    2. Item-level evaluators: Score each query/response pair individually
    3. Run-level evaluators: Aggregate metrics across all items

    Evaluates embedding-based retrieval (vector similarity search) directly.
    """

    def __init__(
        self,
        trace_name: str | None = None,
    ):
        """
        Initialize the evaluator.

        Args:
            trace_name: Name for Langfuse traces (defaults to TRACE_NAME env var or "rag")
        """
        self.trace_name = trace_name or os.getenv("TRACE_NAME") or "rag"

    def create_task_function(self):
        """
        Create task function for run_experiment.

        The task function is what Langfuse calls for EACH dataset item.
        It's the "system under test" - it runs embedding search on a question
        and returns the output that evaluators will score.

        Returns:
            Task function that performs embedding-based retrieval
        """
        return self._create_embedding_eval_task()

    def _create_embedding_eval_task(self):
        """Create task function for embedding evaluation."""

        def task(*, item, **_kwargs):
            """
            Embedding evaluation task - evaluate embedding search directly.

            Works with existing end-to-end datasets!
            - Uses "question" or "query" from input
            - Calls search_all_entity_types directly (embedding similarity search)
            - Returns collections and answer for Ragas metrics

            Returns:
                dict with collections, answer, and question (same format as end-to-end)
            """
            # Extract query from dataset item
            query = item.input["question"]

            # Execute embedding similarity search directly
            results = search_all_entity_types(
                query_text=query,
                similarity_threshold=0.3,
                limit=15,
            )

            # Get concept IDs for hydration
            concept_ids = [
                r["external_id"] for r in results if r["type"] == "collection"
            ]

            # Hydrate collections from database to get proper title/abstract

            datastore = get_datastore()
            collection_data = datastore.fetch_collections_by_ids(concept_ids)

            # Convert results to collection format for Ragas evaluation
            collections = []
            for r in results:
                if r["type"] == "collection":
                    concept_id = r["external_id"]
                    data = collection_data.get(concept_id, {})
                    metadata = data.get("metadata", {})

                    collections.append(
                        {
                            "title": metadata.get("EntryTitle", concept_id),
                            "abstract": metadata.get(
                                "Abstract",
                                r.get("text_content", "No description available"),
                            ),
                            "concept_id": concept_id,
                            "similarity_score": r["similarity"],
                        }
                    )

            # Generate a simple answer from collections
            if collections:
                answer = f"Found {len(collections)} relevant data collections based on embedding search."
            else:
                answer = "No relevant data collections found in embedding search."

            # Return output with both answer and collections for evaluators
            result = {
                "answer": answer,
                "collections": collections,
                "question": query,
            }

            # Add reference (ground truth answer) if present in dataset
            if item.expected_output and "reference" in item.expected_output:
                result["reference"] = item.expected_output["reference"]

            return result

        return task

    def create_evaluators(self):
        """
        Create evaluator functions for run_experiment.

        Returns:
            List of evaluator functions
        """
        return self._create_embedding_evaluators()

    def _create_embedding_evaluators(self):
        """Create evaluators for embedding evaluation.

        Returns individual evaluator functions for:
        1. Individual collection relevance scores
        2. Context precision (with reference)
        3. Context recall (with reference)
        """
        evaluators = []

        # Evaluator for individual collection relevance scores
        async def collection_relevance_evaluator(*, output, **_kwargs):
            """Score each collection individually for relevance."""
            try:
                question = output.get("question", "")
                collections = output.get("collections", [])

                if not collections:
                    logger.info("No collections to evaluate")
                    return []

                # Get all collection relevance scores using shared logic
                relevance_data = (
                    await SingleEvaluation.compute_dataset_relevance_scores(
                        question=question,
                        collections=collections,
                    )
                )

                individual_scores = relevance_data.get("individual_scores", [])

                # Create individual Evaluation objects only for successfully scored collections.
                # `individual_scores` is kept positionally aligned with `collections`, so a
                # score may be None when a collection could not be evaluated.
                evaluations = []
                for i, collection in enumerate(collections):
                    if i >= len(individual_scores):
                        break

                    score = individual_scores[i]
                    if score is None:
                        continue

                    comment = (
                        f"Query: '{question}' | "
                        f"Concept: {collection.get('concept_id', 'unknown')} | "
                        f"Title: {collection.get('title', '')} | "
                        f"Abstract: {collection.get('abstract', '')[:200]}..."
                    )

                    evaluations.append(
                        Evaluation(
                            name=f"embedding_collection_{i+1}_relevance",
                            value=score,
                            comment=comment,
                        )
                    )

                logger.info(
                    "Scored %d/%d collections",
                    len([score for score in individual_scores if score is not None]),
                    len(collections),
                )
                return evaluations

            except Exception as e:
                logger.error(
                    "Error in collection_relevance_evaluator: %s", e, exc_info=True
                )
                return []

        # Evaluator for context precision with reference
        async def embedding_context_precision_evaluator(*, output, **_kwargs):
            """Evaluate context precision using reference (ground truth)."""
            try:
                question = output.get("question", "")
                collections = output.get("collections", [])
                reference = output.get("reference")

                if not reference or not collections:
                    return None

                contexts = generate_contexts_from_collections(
                    collections, fields=["title", "abstract"]
                )

                score = await SingleEvaluation.compute_context_precision_with_reference(
                    question=question,
                    contexts=contexts,
                    reference=reference,
                )

                if score is None:
                    return None

                return Evaluation(
                    name="embedding_context_precision",
                    value=score,
                    comment=(
                        "Context Precision measures how well a retriever ranks relevant "
                        "chunks above irrelevant ones by evaluating whether relevant "
                        "information appears near the top of the results."
                    ),
                )

            except Exception as e:
                logger.error(
                    "Error in context_precision_evaluator: %s", e, exc_info=True
                )
                return None

        # Evaluator for context recall
        async def embedding_context_recall_evaluator(*, output, **_kwargs):
            """Evaluate context recall using reference (approximation based on claims)."""
            try:
                question = output.get("question", "")
                collections = output.get("collections", [])
                reference = output.get("reference")

                if not reference or not collections:
                    return None

                contexts = generate_contexts_from_collections(
                    collections, fields=["title", "abstract"]
                )

                score = await SingleEvaluation.compute_context_recall(
                    question=question,
                    contexts=contexts,
                    reference=reference,
                )

                if score is None:
                    return None

                return Evaluation(
                    name="embedding_context_recall",
                    value=score,
                    comment=(
                        "Context Recall measures how well a retrieval system avoids missing "
                        "important information by checking whether all key claims in a "
                        "reference answer can be supported by the retrieved context."
                    ),
                )

            except Exception as e:
                logger.error("Error in context_recall_evaluator: %s", e, exc_info=True)
                return None

        evaluators.extend(
            [
                collection_relevance_evaluator,
                embedding_context_precision_evaluator,
                embedding_context_recall_evaluator,
            ]
        )

        return evaluators

    def create_run_evaluators(self):
        """
        Create run-level evaluator functions (executed once after all items).

        Run-level evaluators aggregate metrics across all dataset items.
        They receive item_results containing all item-level evaluations.

        Returns:
            List of run-level evaluator functions
        """
        # No run-level evaluators for either mode
        return []

    def run_experiment(
        self,
        dataset_name: str,
        experiment_name: str | None = None,
        experiment_description: str | None = None,
        max_concurrency: int = 3,
    ):
        """
        Run Langfuse experiment on a dataset.

        Implements Langfuse experiments SDK pattern:
        - Task: Executes RAG system on each dataset item
        - Item evaluators: Score each query/response pair
        - Run evaluators: Aggregate across all items

        Args:
            dataset_name: Langfuse dataset name
            experiment_name: Experiment identifier (auto-generated if not provided)
            experiment_description: Human-readable description
            max_concurrency: Parallel execution limit

        Returns:
            Experiment result with aggregated metrics
        """
        langfuse = get_langfuse()
        dataset = langfuse.get_dataset(dataset_name)

        # Auto-generate experiment name if needed
        if not experiment_name:
            experiment_name = f"{self.trace_name}_embedding_eval_{dataset_name}"

        # Generate unique run name with timestamp
        run_name = f"{experiment_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Prepare experiment components
        task = self.create_task_function()
        evaluators = self.create_evaluators()
        run_evaluators = self.create_run_evaluators()

        # Log experiment configuration
        logger.info("Starting experiment: %s", experiment_name)
        logger.info("Run name: %s", run_name)
        logger.info("Mode: embedding_evaluation")
        logger.info("Dataset: %s (%d items)", dataset_name, len(dataset.items))
        logger.info("Item evaluators: %d", len(evaluators))
        logger.info("Run evaluators: %d", len(run_evaluators))

        # Execute experiment
        result = dataset.run_experiment(
            name=experiment_name,
            run_name=run_name,
            description=experiment_description or "Embedding retrieval evaluation",
            task=task,
            evaluators=evaluators,
            run_evaluators=run_evaluators,
            max_concurrency=max_concurrency,
        )

        # Display results
        logger.info("=" * 70)
        logger.info("Experiment Complete")
        logger.info("=" * 70)
        print(result.format())

        flush_langfuse()
        return result


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

    @classmethod
    async def compute_single_collection_relevance(
        cls,
        question: str,
        collection: dict,
        collection_fields: list[str] | None = None,
    ) -> float | None:
        """
        Compute relevance score for a single collection.

        Args:
            question: User query
            collection: Single collection dict
            collection_fields: Fields to extract from collection (default: ["title", "abstract"])

        Returns:
            Relevance score (0-1) or None if error
        """
        cls._initialize_components()

        # Default collection fields
        if collection_fields is None:
            collection_fields = ["title", "abstract"]

        try:
            # Extract only the specified fields for relevance scoring
            dataset_subset = {
                field: collection.get(field, "") for field in collection_fields
            }

            prompt_input = DatasetRelevanceInput(
                question=question,
                dataset=dataset_subset,
            )

            # Call with exponential backoff retry
            score = await cls._call_relevance_prompt_with_retry(prompt_input)
            return score

        except Exception as e:
            # Catch any unexpected errors outside retry logic
            concept_id = collection.get("concept_id", "unknown")
            logger.error("Unexpected error scoring collection %s: %s", concept_id, e)
            return None

    @classmethod
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type(Exception),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def _call_relevance_prompt_with_retry(cls, prompt_input) -> float:
        """
        Call relevance prompt with automatic retry.

        Uses tenacity for exponential backoff:
        - Attempt 1: immediate
        - Attempt 2: ~1s delay (1 * 2^0)
        - Attempt 3: ~2s delay (1 * 2^1)
        - Max wait capped at 4s

        Args:
            prompt_input: DatasetRelevanceInput for the prompt

        Returns:
            Relevance score (0-1)

        Raises:
            Exception: If all retries exhausted
        """
        result = await cls._relevance_prompt.generate(
            data=prompt_input,
            llm=cls._llm,
            retries_left=3,  # Inner retry for output parsing failures
        )
        return result.relevance_score

    @classmethod
    async def compute_dataset_relevance_scores(
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

        # Score individual collections using the single collection helper.
        # Keep positional alignment with `collections` so downstream evaluators can
        # safely associate each score with its original item.
        collection_scores = []
        for collection in collections:
            score = await cls.compute_single_collection_relevance(
                question=question,
                collection=collection,
                collection_fields=collection_fields,
            )
            collection_scores.append(score)

        # Compute aggregates
        result = {
            "individual_scores": collection_scores,
            "avg_relevance": None,
            "max_relevance": None,
        }

        valid_scores = [score for score in collection_scores if score is not None]

        if valid_scores:
            result["avg_relevance"] = sum(valid_scores) / len(valid_scores)
            result["max_relevance"] = max(valid_scores)

        return result

    @classmethod
    async def compute_faithfulness(
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
            metric = Faithfulness(llm=cls._llm, embeddings=cls._embeddings)
            result = await metric.ascore(
                user_input=question,
                retrieved_contexts=contexts,
                response=answer,
            )
            return result.value
        except Exception as e:
            logger.warning("Error computing faithfulness: %s", e)
            return None

    @classmethod
    async def compute_answer_relevancy(
        cls,
        question: str,
        answer: str,
    ) -> float | None:
        """
        Compute answer relevancy score using Ragas.

        Args:
            question: User query
            answer: Generated answer

        Returns:
            Answer relevancy score (0-1) or None if error
        """
        cls._initialize_components()

        try:
            metric = AnswerRelevancy(llm=cls._llm, embeddings=cls._embeddings)
            result = await metric.ascore(
                user_input=question,
                response=answer,
            )
            return result.value
        except Exception as e:
            logger.warning("Error computing answer relevancy: %s", e)
            return None

    @classmethod
    async def compute_context_precision_with_reference(
        cls,
        question: str,
        contexts: list[str],
        reference: str,
    ) -> float | None:
        """
        Compute context precision with reference using Ragas.

        Args:
            question: User query
            contexts: Retrieved contexts
            reference: Reference answer (ground truth)

        Returns:
            Context precision score (0-1) or None if error
        """
        cls._initialize_components()

        try:
            metric = ContextPrecision(llm=cls._llm)
            result = await metric.ascore(
                user_input=question,
                retrieved_contexts=contexts,
                reference=reference,
            )
            return result.value
        except Exception as e:
            logger.warning("Error computing context precision with reference: %s", e)
            return None

    @classmethod
    async def compute_context_recall(
        cls,
        question: str,
        contexts: list[str],
        reference: str,
    ) -> float | None:
        """
        Compute context recall using Ragas.

        Args:
            question: User query
            contexts: Retrieved contexts
            reference: Reference answer (ground truth)

        Returns:
            Context recall score (0-1) or None if error
        """
        cls._initialize_components()

        try:
            metric = ContextRecall(llm=cls._llm)
            result = await metric.ascore(
                user_input=question,
                retrieved_contexts=contexts,
                reference=reference,
            )
            return result.value
        except Exception as e:
            logger.warning("Error computing context recall: %s", e)
            return None


def main():
    """Main entry point for running evaluations."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Apply nest_asyncio to allow nested event loops (for PydanticPrompt.generate in evaluators)
    nest_asyncio.apply()

    # Get configuration from environment
    dataset_name = os.getenv("DATASET_NAME")
    experiment_name = os.getenv("EXPERIMENT_NAME")
    max_concurrency = int(os.getenv("EVAL_MAX_CONCURRENCY", "3"))

    if not dataset_name:
        raise ValueError(
            "DATASET_NAME environment variable not set. "
            "Example: earthdata/manual-test"
        )

    # Initialize evaluator
    evaluator = EarthdataEvaluator()

    # Run experiment using run_experiment API
    evaluator.run_experiment(
        dataset_name=dataset_name,
        experiment_name=experiment_name,
        max_concurrency=max_concurrency,
    )


if __name__ == "__main__":  # pragma: no cover
    main()
