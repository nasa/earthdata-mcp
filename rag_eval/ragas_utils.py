"""Utilities for initializing and running Ragas metrics."""

import logging
from typing import List

from ragas.dataset_schema import SingleTurnSample
from ragas.llms import llm_factory
from ragas.embeddings import embedding_factory
from ragas.run_config import RunConfig
from ragas.metrics.base import MetricWithLLM, MetricWithEmbeddings
import litellm

logger = logging.getLogger(__name__)


def create_bedrock_llm(
    model: str = "amazon.nova-pro-v1:0",
    temperature: float = 0.01,
    max_tokens: int = 10000,
):
    """
    Create a Bedrock LLM for Ragas evaluation.

    Args:
        model: Bedrock model name (without 'bedrock/' prefix)
        temperature: LLM temperature
        max_tokens: Maximum tokens for structured outputs

    Returns:
        Initialized LLM instance
    """
    return llm_factory(
        f"bedrock/{model}",
        provider="litellm",
        client=litellm.completion,
        temperature=temperature,
        max_tokens=max_tokens,
    )


def create_bedrock_embeddings(model: str = "amazon.titan-embed-text-v2:0"):
    """
    Create Bedrock embeddings for Ragas evaluation.

    Args:
        model: Bedrock embeddings model name (without 'bedrock/' prefix)

    Returns:
        Initialized embeddings instance
    """
    return embedding_factory(
        "litellm",
        model=f"bedrock/{model}",
    )


def init_ragas_metrics(metrics, llm, embedding):
    """
    Initialize Ragas metrics with LLM and embeddings.

    Args:
        metrics: List of Ragas metric instances
        llm: LLM instance
        embedding: Embeddings instance
    """
    for metric in metrics:
        if isinstance(metric, MetricWithLLM):
            metric.llm = llm
        if isinstance(metric, MetricWithEmbeddings):
            metric.embeddings = embedding
        run_config = RunConfig()
        metric.init(run_config)


async def score_with_ragas(
    metrics, query: str, contexts: List[str], answer: str
) -> dict:
    """
    Score a single sample with Ragas metrics.

    Args:
        metrics: List of initialized Ragas metrics
        query: User query
        contexts: Retrieved contexts
        answer: Generated answer

    Returns:
        Dict mapping metric names to scores
    """
    scores = {}
    for m in metrics:
        sample = SingleTurnSample(
            user_input=query,
            retrieved_contexts=contexts,
            response=answer,
        )
        logger.info(f"Calculating {m.name}...")
        scores[m.name] = await m.single_turn_ascore(sample)
    return scores
