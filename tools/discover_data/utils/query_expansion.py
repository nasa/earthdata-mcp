"""
Query expansion utilities for discover_data orchestrator.

When a user query is too broad or vague, this module analyzes what
related data exists and generates clarifying questions to help
the user refine their search.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

from tools.models.output_model import ClarifyingQuestion

logger = logging.getLogger(__name__)


@dataclass
class DiscoveryContext:
    """Context about what was found for a broad/vague query."""

    # What science keywords matched?
    science_keywords: list[dict[str, Any]] = field(default_factory=list)

    # What instruments matched?
    instruments: list[dict[str, Any]] = field(default_factory=list)

    # What platforms matched?
    platforms: list[dict[str, Any]] = field(default_factory=list)

    # What variables matched?
    variables: list[dict[str, Any]] = field(default_factory=list)

    # Low-confidence collection matches (0.3-0.5)
    weak_collection_matches: list[dict[str, Any]] = field(default_factory=list)

    # Temporal resolutions available in weak matches
    available_temporal_resolutions: set[str] = field(default_factory=set)

    # Spatial resolutions available in weak matches
    available_spatial_resolutions: set[str] = field(default_factory=set)


def analyze_embedding_results(
    embedding_results: list[dict[str, Any]],
    min_similarity: float = 0.3,
) -> DiscoveryContext:
    """
    Analyze embedding results to understand what data is available.

    Args:
        embedding_results: Raw results from search_all_entity_types
        min_similarity: Minimum similarity to consider

    Returns:
        DiscoveryContext with categorized matches
    """
    context = DiscoveryContext()

    for result in embedding_results:
        if result.get("similarity", 0) < min_similarity:
            continue

        entity_type = result.get("type")
        text = result.get("text_content", "")
        similarity = result.get("similarity", 0)

        entry = {
            "external_id": result.get("external_id"),
            "text": text[:200] if text else "",  # Truncate for display
            "similarity": similarity,
        }

        if entity_type == "collection":
            context.weak_collection_matches.append(entry)
        elif entity_type == "sciencekeywords":
            context.science_keywords.append(entry)
        elif entity_type == "instruments":
            context.instruments.append(entry)
        elif entity_type == "platforms":
            context.platforms.append(entry)
        elif entity_type == "variable":
            context.variables.append(entry)

    return context


def generate_expansion_questions(
    original_query: str,
    context: DiscoveryContext,
) -> list[ClarifyingQuestion]:
    """
    Generate clarifying questions to help user refine a broad query.

    Args:
        original_query: The user's original query text
        context: DiscoveryContext with what was found

    Returns:
        List of clarifying questions
    """
    questions = []

    # Question 1: What type of data are you looking for?
    if context.science_keywords:
        # Extract unique keyword topics
        keyword_options = _extract_keyword_options(context.science_keywords)
        if len(keyword_options) > 1:
            questions.append(
                ClarifyingQuestion(
                    question_id="data_type",
                    question_text=f"I found several types of data related to '{original_query}'. What are you looking for?",
                    question_type="data_type_preference",
                    options=keyword_options[:4],  # Max 4 options
                    explanations=None,
                    recommendation=None,
                    related_collection_ids=[],
                )
            )

    # Question 2: What instrument/sensor?
    if context.instruments and len(context.instruments) > 1:
        instrument_names = sorted(
            {_extract_name_from_text(inst["text"]) for inst in context.instruments}
        )[:4]
        if len(instrument_names) > 1:
            questions.append(
                ClarifyingQuestion(
                    question_id="instrument_preference",
                    question_text="Data is available from multiple instruments. Do you have a preference?",
                    question_type="instrument_preference",
                    options=instrument_names,
                    explanations=None,
                    recommendation=None,
                    related_collection_ids=[],
                )
            )

    # Question 3: What temporal resolution?
    if context.available_temporal_resolutions and len(context.available_temporal_resolutions) > 1:
        questions.append(
            ClarifyingQuestion(
                question_id="temporal_resolution",
                question_text="What time interval works for your analysis?",
                question_type="resolution_preference",
                options=sorted(context.available_temporal_resolutions)[:4],
                explanations={
                    "Daily": "Best for studying individual events or short-term changes",
                    "8-Day": "Good balance of detail and data volume",
                    "Monthly": "Best for seasonal patterns and long-term trends",
                },
                recommendation=None,
                related_collection_ids=[],
            )
        )

    # Question 4: What variable specifically?
    if context.variables and len(context.variables) > 1:
        variable_names = sorted(
            {_extract_name_from_text(var["text"]) for var in context.variables}
        )[:4]
        if len(variable_names) > 1:
            questions.append(
                ClarifyingQuestion(
                    question_id="variable_preference",
                    question_text="Which specific measurement are you interested in?",
                    question_type="variable_preference",
                    options=variable_names,
                    explanations=None,
                    recommendation=None,
                    related_collection_ids=[],
                )
            )

    return questions


def _extract_keyword_options(science_keywords: list[dict]) -> list[str]:
    """Extract readable option names from science keyword matches."""
    options = set()
    for kw in science_keywords:
        text = kw.get("text", "")
        # Science keywords often have format "TOPIC > SUBTOPIC > SPECIFIC"
        # or just the term itself
        if ">" in text:
            parts = text.split(">")
            # Use the most specific part
            options.add(parts[-1].strip())
        else:
            # Use first few words
            words = text.split()[:3]
            options.add(" ".join(words))
    return sorted(options)


def _extract_name_from_text(text: str) -> str:
    """Extract a readable name from entity text content."""
    if not text:
        return "Unknown"
    # If it's "NAME: description" format, extract NAME
    if ":" in text:
        return text.split(":")[0].strip()
    # Otherwise use first few words
    words = text.split()[:3]
    return " ".join(words)


def should_expand_query(
    scored_collections: list[dict[str, Any]],
    embedding_results: list[dict[str, Any]],
    confidence_threshold: float = 0.5,  # pylint: disable=unused-argument
) -> bool:
    """
    Determine if we should offer query expansion instead of no_results.

    Returns True if:
    - Few/no collections passed the confidence threshold
    - But there ARE related entities (keywords, instruments, etc.) that matched

    Args:
        scored_collections: Collections that passed scoring threshold
        embedding_results: Raw embedding search results
        confidence_threshold: The threshold used for scoring

    Returns:
        True if query expansion would be helpful
    """
    # If we have good results, no need to expand
    if len(scored_collections) >= 3:
        return False

    # Check if there are related entities that matched
    non_collection_matches = [
        result
        for result in embedding_results
        if result.get("type") != "collection" and result.get("similarity", 0) >= 0.3
    ]

    # If we have related entities, we can help the user refine
    return len(non_collection_matches) >= 2
