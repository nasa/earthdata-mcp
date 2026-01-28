"""
Disambiguation utilities for discover_data orchestrator.

Groups similar collections and generates clarifying questions when
multiple collections have different resolutions or come from different
platforms/instruments.
"""

import logging
import re

from tools.models.output_model import ClarifyingQuestion, CollectionMatch
from util.kms.client import lookup_term

logger = logging.getLogger(__name__)


def check_disambiguation(
    collections: list[CollectionMatch],
) -> tuple[bool, list[ClarifyingQuestion]]:
    """
    Detect and generate clarifying questions for ambiguous results.

    Strategy:
    1. Group collections by normalized topic (e.g., "sea_surface_temperature")
    2. Within each group, detect:
       - Temporal resolution differences (daily vs weekly vs monthly)
       - Spatial resolution differences
       - Platform/instrument differences (e.g., MODIS vs VIIRS)
    3. If multiple resolutions exist, generate a select question for the user

    Returns:
        (needs_disambiguation, questions) where questions is empty if no
        ambiguity detected.
    """
    questions: list[ClarifyingQuestion] = []

    # Group collections by normalized topic
    topic_groups = group_by_normalized_topic(collections)

    for topic, group in topic_groups.items():
        if len(group) < 2:
            continue  # No disambiguation needed for single-collection groups

        # Check for temporal resolution differences
        temporal_resolutions = set()
        for collection in group:
            if collection.resolution and collection.resolution.temporal_resolution:
                temporal_resolutions.add(collection.resolution.temporal_resolution)

        if len(temporal_resolutions) > 1:
            questions.append(
                _generate_resolution_question(
                    topic=topic,
                    resolution_type="temporal",
                    resolutions=temporal_resolutions,
                    collections=group,
                )
            )

        # Check for spatial resolution differences
        spatial_resolutions = set()
        for collection in group:
            if collection.resolution and collection.resolution.spatial_resolution:
                spatial_resolutions.add(collection.resolution.spatial_resolution)

        if len(spatial_resolutions) > 1:
            questions.append(
                _generate_resolution_question(
                    topic=topic,
                    resolution_type="spatial",
                    resolutions=spatial_resolutions,
                    collections=group,
                )
            )

        # Check for platform differences
        platforms = set()
        for collection in group:
            platforms.update(collection.platforms)

        if len(platforms) > 1:
            questions.append(
                _generate_platform_question(
                    topic=topic,
                    platforms=platforms,
                    collections=group,
                )
            )

    return len(questions) > 0, questions


def group_by_normalized_topic(
    collections: list[CollectionMatch],
) -> dict[str, list[CollectionMatch]]:
    """
    Group collections by their core topic, ignoring resolution/version differences.

    Normalization removes:
    - Version numbers: V001, v6.1, Version 6
    - Resolution values: 250m, 1km, 0.25deg, 4km
    - Processing levels: L2, L3, Level 3
    - Temporal indicators in titles: Daily, Monthly, 8-Day

    Args:
        collections: List of collection matches

    Returns:
        Dictionary mapping normalized topic to list of collections
    """
    groups: dict[str, list[CollectionMatch]] = {}

    for collection in collections:
        topic = normalize_title(collection.title)
        if topic not in groups:
            groups[topic] = []
        groups[topic].append(collection)

    return groups


def normalize_title(title: str) -> str:
    """
    Normalize a collection title to extract the core topic.

    Removes version numbers, resolutions, processing levels, and temporal indicators.

    Args:
        title: Collection title

    Returns:
        Normalized topic string
    """
    t = title.lower()

    # Remove version patterns (V001, v6.1, Version 6)
    t = re.sub(r"\bv(?:ersion)?\s*[\d.]+\b", "", t)

    # Remove resolution patterns (250m, 1km, 0.25deg, 4km)
    t = re.sub(r"\b[\d.]+\s*(m|km|deg|degree|arc[- ]?sec)\b", "", t)

    # Remove processing levels (L2, L3, L2G, L2SP, L3A, Level 3)
    t = re.sub(r"\bl(?:evel)?\s*[\d]+[a-z]*\b", "", t)

    # Remove temporal indicators (Daily, Monthly, 8-Day)
    t = re.sub(r"\b(daily|monthly|weekly|yearly|8-day|8 day|\d+-day)\b", "", t)

    # Remove common suffixes that don't affect topic
    t = re.sub(r"\b(global|regional|local)\b", "", t)

    # Collapse whitespace and trim
    t = re.sub(r"\s+", " ", t).strip()

    return t


def _generate_resolution_question(
    topic: str,
    resolution_type: str,
    resolutions: set[str],
    collections: list[CollectionMatch],
) -> ClarifyingQuestion:
    """
    Generate a clarifying question for resolution differences.

    Args:
        topic: Normalized topic name
        resolution_type: "temporal" or "spatial"
        resolutions: Set of different resolution values
        collections: List of collections in this topic group

    Returns:
        ClarifyingQuestion for resolution preference
    """
    # Generate a readable topic name (capitalize words)
    readable_topic = " ".join(word.capitalize() for word in topic.split())

    if resolution_type == "temporal":
        question_text = (
            f"I found {len(collections)} '{readable_topic}' datasets with different "
            f"time intervals. Which works best for your analysis?"
        )
    else:
        question_text = (
            f"These '{readable_topic}' datasets have different spatial detail levels. "
            f"What resolution do you need?"
        )

    return ClarifyingQuestion(
        question_id=f"{resolution_type}_res_{hash(topic) % 100000}",
        question_text=question_text,
        question_type="resolution_preference",
        options=sorted(resolutions),
        explanations=None,  # No KMS definitions for resolution values
        recommendation=None,
        related_collection_ids=[c.concept_id for c in collections],
    )


def _generate_platform_question(
    topic: str,
    platforms: set[str],
    collections: list[CollectionMatch],
) -> ClarifyingQuestion:
    """
    Generate a clarifying question for platform differences.

    Uses KMS to look up platform definitions for explanations.

    Args:
        topic: Normalized topic name
        platforms: Set of platform names
        collections: List of collections in this topic group

    Returns:
        ClarifyingQuestion for platform preference
    """
    readable_topic = " ".join(word.capitalize() for word in topic.split())

    explanations: dict[str, str] = {}
    for platform in platforms:
        kms_term = lookup_term(platform, "platforms")
        if kms_term and kms_term.definition:
            explanations[platform] = kms_term.definition
        # If no KMS definition, don't add to explanations (per spec)

    return ClarifyingQuestion(
        question_id=f"platform_{hash(topic) % 100000}",
        question_text=f"'{readable_topic}' data is available from multiple satellites. Which platform?",
        question_type="platform_preference",
        options=sorted(platforms),
        explanations=explanations if explanations else None,
        recommendation=None,
        related_collection_ids=[c.concept_id for c in collections],
    )


def filter_by_user_refinements(
    collections: list[CollectionMatch],
    refinements: dict[str, str],
) -> list[CollectionMatch]:
    """
    Filter collections based on user's answers to clarifying questions.

    Args:
        collections: List of collection matches
        refinements: Dict mapping question_id to selected option

    Returns:
        Filtered list of collections matching user preferences
    """
    if not refinements:
        return collections

    filtered = collections

    for question_id, selected_option in refinements.items():
        if question_id.startswith("temporal_res_"):
            filtered = [
                c
                for c in filtered
                if c.resolution is None
                or c.resolution.temporal_resolution is None
                or c.resolution.temporal_resolution == selected_option
            ]
        elif question_id.startswith("spatial_res_"):
            filtered = [
                c
                for c in filtered
                if c.resolution is None
                or c.resolution.spatial_resolution is None
                or c.resolution.spatial_resolution == selected_option
            ]
        elif question_id.startswith("platform_"):
            filtered = [c for c in filtered if not c.platforms or selected_option in c.platforms]

    return filtered
