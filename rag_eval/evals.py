"""Offline RAG evaluation for Earthdata MCP server."""

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

from mcp_client import EarthdataRAGClient
from models import DatasetRelevanceInput, DatasetRelevancePrompt
from ragas_utils import (
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

    async def _score_dataset(self, question: str, title: str, abstract: str) -> float:
        """Score a single dataset's relevance to a question."""
        prompt_input = DatasetRelevanceInput(
            question=question,
            dataset_title=title,
            dataset_abstract=abstract,
        )
        result = await self.relevance_prompt.generate(data=prompt_input, llm=self.llm)
        return result.relevance_score

    def close(self):
        """Close the RAG client connection"""
        if hasattr(self, "rag_client"):
            self.rag_client.close()

    async def evaluate(self, testset_path: str):
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

                    # Score individual datasets
                    logger.info("Scoring individual datasets...")
                    dataset_scores = []
                    for collection_idx, collection in enumerate(collections):
                        score = await self._score_dataset(
                            question=question,
                            title=collection.get("title", ""),
                            abstract=collection.get("abstract", ""),
                        )
                        dataset_scores.append(score)

                        # Log scoring generation
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
                            # Score this individual dataset
                            scoring_span.score(
                                name="dataset_relevance",
                                value=score,
                                data_type="NUMERIC",
                                comment=f"Dataset {collection_idx + 1}: {collection.get('title', 'N/A')[:50]}",
                            )

                    # Calculate aggregate dataset scores
                    avg_dataset_relevance = (
                        sum(dataset_scores) / len(dataset_scores)
                        if dataset_scores
                        else 0.0
                    )
                    max_dataset_relevance = (
                        max(dataset_scores) if dataset_scores else 0.0
                    )

                    # Compute Ragas metrics for overall RAG quality
                    logger.info("Computing Ragas metrics...")
                    ragas_scores = await score_with_ragas(
                        self.metrics, question, contexts, answer
                    )

                    logger.info(f"RAGAS Scores: {ragas_scores}")

                    # Add all scores to Langfuse trace
                    trace.score(
                        name="avg_dataset_relevance",
                        value=avg_dataset_relevance,
                        data_type="NUMERIC",
                        comment="Average relevance of individual datasets",
                    )
                    trace.score(
                        name="max_dataset_relevance",
                        value=max_dataset_relevance,
                        data_type="NUMERIC",
                        comment="Best dataset relevance score",
                    )

                    # Ragas metrics
                    for metric_name, score_value in ragas_scores.items():
                        trace.score(
                            name=metric_name,
                            value=score_value,
                            data_type="NUMERIC",
                            comment=f"Ragas {metric_name} metric",
                        )

                    # Store result
                    result_row = {
                        **row,
                        "response": answer,
                        "num_datasets_returned": len(collections),
                        "avg_dataset_relevance": avg_dataset_relevance,
                        "max_dataset_relevance": max_dataset_relevance,
                        "individual_dataset_scores": dataset_scores,
                        "ragas_scores": ragas_scores,
                        "trace_id": trace_id,
                    }
                    results.append(result_row)

                    logger.info(f"→ Avg Dataset Relevance: {avg_dataset_relevance:.3f}")
                    logger.info(f"→ Max Dataset Relevance: {max_dataset_relevance:.3f}")
                    logger.info(
                        f"→ Faithfulness: {ragas_scores.get('faithfulness', 0):.3f}"
                    )
                    logger.info(
                        f"→ Context Precision: {ragas_scores.get('context_precision', 0):.3f}"
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


async def main():
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
        results = await evaluator.evaluate(testset_path)
        logger.info(f"Evaluation complete: {len(results)} results")
    finally:
        # Clean up resources
        evaluator.close()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
