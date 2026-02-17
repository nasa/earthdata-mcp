"""Offline RAG evaluation for Earthdata MCP server."""

import asyncio
import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from ragas import Dataset
from ragas.metrics import (
    Faithfulness,
    LLMContextPrecisionWithoutReference,
)

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


class EarthdataEvaluator:
    """Evaluator for Earthdata RAG system using Ragas metrics"""

    def __init__(
        self,
        mcp_server_url: str,
        llm_model: str = "amazon.nova-pro-v1:0",
        temperature: float = 0.01,
    ):
        """
        Initialize the evaluator.

        Args:
            mcp_server_url: URL of the MCP server to evaluate
            llm_model: Bedrock LLM model for evaluation scoring
            temperature: LLM temperature
        """
        # Create Bedrock LLM and embeddings
        self.llm = create_bedrock_llm(
            model=llm_model,
            temperature=temperature,
            max_tokens=10000,
        )
        self.embeddings = create_bedrock_embeddings()

        # Set up RAG client
        self.rag_client = EarthdataRAGClient(server_url=mcp_server_url)

        # Initialize custom per-dataset relevance prompt
        self.relevance_prompt = DatasetRelevancePrompt()

        # Initialize Ragas metrics for overall RAG evaluation
        self.metrics = [
            Faithfulness(),
            LLMContextPrecisionWithoutReference(),
        ]
        init_ragas_metrics(self.metrics, self.llm, self.embeddings)

    def load_dataset(self, testset_path: str) -> Dataset:
        """Load test dataset from JSON file."""
        testset_file = Path(testset_path)
        if not testset_file.exists():
            raise FileNotFoundError(f"Test set file not found: {testset_file}")

        logger.info(f"Loading test set from: {testset_file}")

        with open(testset_file, "r") as f:
            testset_data = json.load(f)

        dataset = Dataset(
            name="earthdata_manual_testset",
            backend="inmemory",
        )

        # Load test cases from the Ragas-formatted JSON
        for test_case in testset_data["test_cases"]:
            row = {
                "question_id": test_case["question_id"],
                "user_input": test_case["user_input"],
                "reference_contexts": test_case["reference_contexts"],
                "reference": test_case["reference"],
                "synthesizer_name": test_case.get("synthesizer_name", "manual"),
                "metadata": test_case.get("metadata", {}),
            }
            dataset.append(row)

        logger.info(f"Loaded {len(testset_data['test_cases'])} test cases")
        dataset.save()
        return dataset

    def _score_dataset(self, question: str, title: str, abstract: str) -> float:
        """Score a single dataset's relevance to a question."""
        prompt_input = DatasetRelevanceInput(
            question=question,
            dataset_title=title,
            dataset_abstract=abstract,
        )
        result = self.relevance_prompt.generate(data=prompt_input, llm=self.llm)
        return result.relevance_score

    def close(self):
        """Close the RAG client connection"""
        if hasattr(self, "rag_client"):
            self.rag_client.close()

    def evaluate(self, testset_path: str):
        """Run full evaluation on a test dataset."""
        langfuse = get_langfuse()
        dataset = self.load_dataset(testset_path)
        logger.info(f"Dataset loaded successfully")

        results = []

        for idx, row in enumerate(dataset):
            logger.info("=" * 60)
            logger.info(
                f"Evaluating test case {idx + 1}/{len(dataset)}: {row['question_id']}"
            )
            logger.info(f"Question: {row['user_input']}")

            question = row["user_input"]

            try:
                # Start a new trace for this evaluation
                with langfuse.start_as_current_observation(
                    as_type="span", name="rag"
                ) as trace:
                    trace_id = trace.trace_id

                    # Retrieve datasets
                    response = self.rag_client.query(question)
                    collections = []
                    if "raw_result" in response:
                        collections = response["raw_result"].get("collections", [])

                    # Prepare contexts from retrieved datasets
                    contexts = [
                        f"Title: {c.get('title', 'Unknown')}\nAbstract: {c.get('abstract', 'No description')}"
                        for c in collections
                    ]

                    # Log retrieval span
                    with trace.start_as_current_observation(
                        as_type="span",
                        name="retrieval",
                        input={"question": question},
                        output={"contexts": contexts, "num_datasets": len(collections)},
                    ):
                        pass

                    # Generate answer (already done by MCP server)
                    answer = response.get("answer", "")

                    # Log generation span
                    with trace.start_as_current_observation(
                        as_type="span",
                        name="generation",
                        input={"question": question, "contexts": contexts},
                        output={"answer": answer},
                    ):
                        pass

                    # Use shared evaluation logic
                    all_scores = SingleEvaluation.evaluate_single(
                        question=question,
                        collections=collections,
                        contexts=contexts,
                        answer=answer,
                    )

                    # Add individual dataset scores to trace
                    individual_scores = all_scores.get(
                        "individual_dataset_scores", {}
                    ).get("value", [])
                    for collection_idx, (collection, score) in enumerate(
                        zip(collections, individual_scores)
                    ):
                        with trace.start_as_current_observation(
                            as_type="span",
                            name="score_dataset_relevance",
                            input={
                                "question": question,
                                "title": collection.get("title", ""),
                                "abstract": collection.get("abstract", ""),
                            },
                            output={"relevance_score": score},
                        ) as scoring_span:
                            scoring_span.score(
                                name="dataset_relevance",
                                value=score,
                                data_type="NUMERIC",
                                comment=f"Dataset {collection_idx + 1}: {collection.get('title', 'N/A')[:50]}",
                            )

                    # Add all other scores to trace dynamically
                    for metric_name, metric_data in all_scores.items():
                        # Skip individual scores (already added above)
                        if metric_name == "individual_dataset_scores":
                            continue

                        # Extract metadata
                        value = metric_data.get("value")
                        comment = metric_data.get("comment", "")
                        data_type = metric_data.get("data_type", "NUMERIC")

                        # Only add numeric scores to trace
                        if isinstance(value, (int, float)):
                            trace.score(
                                name=metric_name,
                                value=value,
                                data_type=data_type,
                                comment=comment,
                            )

                    # Store result - dynamically extract all score values
                    result_row = {
                        **row,
                        "response": answer,
                        "num_datasets_returned": len(collections),
                        "trace_id": trace_id,
                    }

                    # Add all scores dynamically
                    for metric_name, metric_data in all_scores.items():
                        value = metric_data.get("value")
                        # Store the value directly in result_row
                        result_row[metric_name] = value

                    results.append(result_row)

                    logger.info(
                        f"→ Avg Dataset Relevance: {all_scores.get('avg_dataset_relevance', {}).get('value', 0):.3f}"
                    )
                    logger.info(
                        f"→ Max Dataset Relevance: {all_scores.get('max_dataset_relevance', {}).get('value', 0):.3f}"
                    )
                    logger.info(
                        f"→ Faithfulness: {all_scores.get('faithfulness', {}).get('value', 0):.3f}"
                    )
                    logger.info(
                        f"→ Context Precision: {all_scores.get('context_precision', {}).get('value', 0):.3f}"
                    )
                    logger.info(f"→ Datasets Retrieved: {len(collections)}")

            except Exception as e:
                logger.error(f"Error evaluating test case: {e}", exc_info=True)
                # Store error result
                result_row = {
                    **row,
                    "response": "",
                    "error": str(e),
                }
                results.append(result_row)
                continue

        # Flush to ensure all data is sent
        flush_langfuse()

        logger.info("=" * 60)
        logger.info(f"Evaluation complete! {len(results)} test cases evaluated")
        logger.info(f"View results in Langfuse UI: {os.getenv('LANGFUSE_BASE_URL')}")

        return results


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
    def evaluate_single(
        cls,
        question: str,
        collections: list[dict],
        contexts: list[str],
        answer: str,
    ) -> dict[str, float]:
        """
        Evaluate a single query/response and return all scores.

        This is the core evaluation that both batch and online evaluation use.
        The caller is responsible for sending scores to Langfuse.

        Args:
            question: User query
            collections: List of collection dicts with 'title' and 'abstract'
            contexts: Retrieved contexts (formatted collection info)
            answer: Generated answer

        Returns:
            Dictionary of all scores, including individual_dataset_scores
        """
        cls._initialize_components()
        all_scores = {}

        # Score individual collections
        collection_scores = []
        for collection in collections:
            try:
                prompt_input = DatasetRelevanceInput(
                    question=question,
                    dataset_title=collection.get("title", ""),
                    dataset_abstract=collection.get("abstract", "") or "No description",
                )
                result = cls._relevance_prompt.generate(data=prompt_input, llm=cls._llm)
                collection_scores.append(result.relevance_score)
            except Exception as e:
                logger.warning(f"Error scoring collection: {e}")
                continue

        # Store individual scores
        all_scores["individual_dataset_scores"] = {
            "value": collection_scores,
            "comment": "Individual relevance scores for each dataset",
            "data_type": "LIST",
        }

        # Compute aggregate collection scores
        if collection_scores:
            avg_relevance = sum(collection_scores) / len(collection_scores)
            max_relevance = max(collection_scores)

            all_scores["avg_dataset_relevance"] = {
                "value": avg_relevance,
                "comment": "Average relevance of individual datasets",
                "data_type": "NUMERIC",
            }
            all_scores["max_dataset_relevance"] = {
                "value": max_relevance,
                "comment": "Best dataset relevance score",
                "data_type": "NUMERIC",
            }

        # Compute Ragas metrics
        try:
            ragas_scores = score_with_ragas(cls._metrics, question, contexts, answer)
            # Wrap Ragas scores with metadata
            for metric_name, score_value in ragas_scores.items():
                all_scores[metric_name] = {
                    "value": score_value,
                    "comment": f"Ragas {metric_name} metric",
                    "data_type": "NUMERIC",
                }
        except Exception as e:
            logger.warning(f"Error computing Ragas scores: {e}")

        return all_scores


def main():
    """Main entry point for running evaluations."""
    # Get configuration from environment
    mcp_server_url = os.getenv(
        "MCP_SERVER_URL", "https://cmr.sit.earthdata.nasa.gov/mcp"
    )
    testset_path = os.getenv("TESTSET_PATH")

    if not testset_path:
        raise ValueError("TESTSET_PATH environment variable not set")

    # Initialize evaluator
    evaluator = EarthdataEvaluator(mcp_server_url=mcp_server_url)

    try:
        # Run evaluation
        results = evaluator.evaluate(testset_path)
        logger.info(f"Evaluation complete: {len(results)} results")
    finally:
        # Clean up resources
        evaluator.close()


if __name__ == "__main__":
    main()
