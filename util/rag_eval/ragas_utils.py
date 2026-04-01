"""Utilities for initializing and running Ragas metrics."""

import logging

import litellm
from ragas.embeddings import embedding_factory
from ragas.llms import llm_factory

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
        Initialized LLM instance (async-compatible)
    """
    return llm_factory(
        f"bedrock/{model}",
        provider="litellm",
        client=litellm.acompletion,  # Use async completion for Ragas
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
