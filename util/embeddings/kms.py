"""KMS-enriched embedding generator.

This generator enriches text with KMS (Keyword Management System) definitions
before generating embeddings. This provides richer semantic context for
science keywords, platforms, and instruments.
"""

import logging
from typing import Any

from util.embeddings.base import EmbeddingGenerator
from util.kms import lookup_term

logger = logging.getLogger(__name__)


class KMSEnrichedEmbeddingGenerator(EmbeddingGenerator):
    """
    Embedding generator that enriches text with KMS definitions before embedding.

    For hierarchical keyword paths like "EARTH SCIENCE > ATMOSPHERE > PRECIPITATION",
    this generator:
    1. Extracts the most specific term (e.g., "PRECIPITATION")
    2. Looks up its definition in KMS
    3. Appends the definition to create enriched text
    4. Generates embedding from the enriched text

    This provides better semantic understanding for downstream similarity searches.

    Example usage with RoutingEmbeddingGenerator:
        router = RoutingEmbeddingGenerator({
            "collection.science_keywords": KMSEnrichedEmbeddingGenerator(
                BedrockEmbeddingGenerator(), scheme="sciencekeywords"
            ),
            "collection.platforms": KMSEnrichedEmbeddingGenerator(
                BedrockEmbeddingGenerator(), scheme="platforms"
            ),
            "default": BedrockEmbeddingGenerator(),
        })
    """

    def __init__(
        self,
        base_generator: EmbeddingGenerator,
        scheme: str = "sciencekeywords",
    ):
        """
        Initialize the KMS-enriched generator.

        Args:
            base_generator: The underlying generator to use after enrichment.
            scheme: KMS concept scheme for lookups (sciencekeywords, platforms, instruments).
        """
        self._base = base_generator
        self._scheme = scheme

    @property
    def model_id(self) -> str:
        """Return the base generator's model identifier."""
        return self._base.model_id

    def generate(
        self,
        text: str,
        concept_type: str | None = None,
        attribute: str | None = None,
        trace: Any | None = None,
    ) -> list[float]:
        """
        Enrich text with KMS definitions, then generate embedding.

        Args:
            text: The text to enrich and embed (may contain multiple terms/paths).
            concept_type: Concept type for the base generator.
            attribute: Attribute name for the base generator.
            trace: Optional Langfuse trace for observability.

        Returns:
            Embedding vector from the base generator.
        """
        enriched_text = self._enrich_text(text)
        return self._base.generate(enriched_text, concept_type, attribute, trace)

    def _enrich_text(self, text: str) -> str:
        """Enrich text by looking up and appending KMS definitions."""
        # Split by newlines (multiple terms) or treat as single term
        lines = text.strip().split("\n") if "\n" in text else [text]
        enriched_lines = [self._enrich_single_term(line.strip()) for line in lines]
        return "\n".join(enriched_lines)

    def _enrich_single_term(self, path: str) -> str:
        """
        Enrich a single term/path with its KMS definition.

        Args:
            path: A term or hierarchical path (e.g., "EARTH SCIENCE > ATMOSPHERE > PRECIPITATION")

        Returns:
            Enriched string with definition appended, or original if not found.
        """
        if not path or not path.strip():
            return path

        term = self._extract_term(path)
        definition = self._fetch_definition(term)

        if definition:
            return f"{term}: {definition}"
        return path

    def _extract_term(self, path: str) -> str:
        """Extract the most specific term from a hierarchical path."""
        if " > " in path:
            return path.split(" > ")[-1].strip()
        return path.strip()

    def _fetch_definition(self, term: str) -> str | None:
        """Fetch definition for a term from KMS."""
        try:
            kms_term = lookup_term(term, self._scheme)
            if kms_term:
                return kms_term.definition
        except Exception as e:
            logger.debug("Failed to fetch KMS definition for '%s': %s", term, e)
        return None
