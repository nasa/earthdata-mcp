"""Embedding generation abstractions."""

from util.embeddings.base import EmbeddingError, EmbeddingGenerator
from util.embeddings.bedrock import BedrockEmbeddingGenerator, RoutingEmbeddingGenerator
from util.embeddings.kms import KMSEnrichedEmbeddingGenerator


def get_embedding_generator() -> EmbeddingGenerator:
    """
    Factory function to get the configured embedding generator.

    Returns a RoutingEmbeddingGenerator that routes different concept types
    and attributes to appropriate generators:
    - KMS-sourced attributes (science_keywords, platforms, instruments) use
      KMSEnrichedEmbeddingGenerator to enrich text with definitions before embedding
    - All other attributes use the default BedrockEmbeddingGenerator

    Returns:
        A configured RoutingEmbeddingGenerator for CMR concept embeddings.
    """
    base = BedrockEmbeddingGenerator()

    return RoutingEmbeddingGenerator(
        generators={
            # KMS-enriched generators for keyword/platform/instrument attributes
            "collection.science_keywords": KMSEnrichedEmbeddingGenerator(
                base, scheme="sciencekeywords"
            ),
            "collection.platforms": KMSEnrichedEmbeddingGenerator(base, scheme="platforms"),
            "collection.instruments": KMSEnrichedEmbeddingGenerator(base, scheme="instruments"),
            "variable.science_keywords": KMSEnrichedEmbeddingGenerator(
                base, scheme="sciencekeywords"
            ),
            # Default for all other attributes (title, abstract, etc.)
            "default": base,
        }
    )


__all__ = [
    "EmbeddingError",
    "EmbeddingGenerator",
    "BedrockEmbeddingGenerator",
    "RoutingEmbeddingGenerator",
    "KMSEnrichedEmbeddingGenerator",
    "get_embedding_generator",
]
