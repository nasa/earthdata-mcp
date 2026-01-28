"""
Collection scoring and ranking utilities for discover_data orchestrator.

Implements discovery-first approach: search all entity types, then score
collections based on direct matches and indirect signals from related entities.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

from langfuse import observe

from tools.discover_data.utils.association_search import get_collections_for_entities

logger = logging.getLogger(__name__)

# Weight factors for different entity types when contributing to indirect score
ENTITY_TYPE_WEIGHTS = {
    "variable": 1.0,  # Variables are strong indicators of collection relevance
    "citation": 0.8,  # Citations indicate collection relevance
    "sciencekeywords": 0.7,  # Science keywords are good topical matches
    "instruments": 0.6,  # Instruments indicate capability
    "platforms": 0.5,  # Platforms are broader (many collections per platform)
}

# Weight for direct vs indirect scores in final ranking
DIRECT_WEIGHT = 1.0
INDIRECT_WEIGHT = 0.8


@dataclass
class CollectionScore:
    """Scoring details for a collection."""

    collection_id: str
    direct_score: float = 0.0
    direct_attribute: str | None = None
    direct_text: str | None = None
    indirect_scores: list[dict[str, Any]] = field(default_factory=list)
    combined_score: float = 0.0

    def add_indirect_signal(
        self,
        entity_id: str,
        entity_type: str,
        entity_text: str,
        similarity: float,
    ) -> None:
        """Add an indirect signal from a related entity."""
        weight = ENTITY_TYPE_WEIGHTS.get(entity_type, 0.5)
        weighted_score = similarity * weight

        self.indirect_scores.append(
            {
                "entity_id": entity_id,
                "entity_type": entity_type,
                "entity_text": entity_text,
                "similarity": similarity,
                "weight": weight,
                "weighted_score": weighted_score,
            }
        )

    def compute_combined_score(self) -> float:
        """Compute the final combined score."""
        # Direct score contribution
        direct_contribution = self.direct_score * DIRECT_WEIGHT

        # Indirect score contribution
        # Use sum of weighted scores, but with diminishing returns
        if self.indirect_scores:
            # Sort by weighted score descending
            sorted_indirect = sorted(
                self.indirect_scores,
                key=lambda x: x["weighted_score"],
                reverse=True,
            )

            # Sum with diminishing returns (each subsequent signal worth less)
            indirect_sum = 0.0
            for i, signal in enumerate(sorted_indirect):
                # Diminishing factor: 1.0, 0.5, 0.33, 0.25, ...
                diminishing = 1.0 / (i + 1)
                indirect_sum += signal["weighted_score"] * diminishing

            indirect_contribution = indirect_sum * INDIRECT_WEIGHT
        else:
            indirect_contribution = 0.0

        self.combined_score = direct_contribution + indirect_contribution
        return self.combined_score

    @property
    def num_signals(self) -> int:
        """Number of indirect signals pointing to this collection."""
        return len(self.indirect_scores)

    @property
    def best_indirect(self) -> dict[str, Any] | None:
        """The highest-scoring indirect signal."""
        if not self.indirect_scores:
            return None
        return max(self.indirect_scores, key=lambda x: x["weighted_score"])

    def to_embedding_result(self) -> dict[str, Any]:
        """Convert to embedding result format for CMR enrichment."""
        # Determine match type and related entity info
        if self.direct_score > 0 and self.indirect_scores:
            match_type = "direct_and_indirect"
        elif self.direct_score > 0:
            match_type = "direct"
        elif self.indirect_scores:
            best = self.best_indirect
            match_type = f"via_{best['entity_type']}"
        else:
            match_type = "unknown"

        result = {
            "external_id": self.collection_id,
            "type": "collection",
            "similarity": self.combined_score,
            "match_type": match_type,
            "attribute": self.direct_attribute,
            "text_content": self.direct_text,
        }

        # Add related entity info if indirect match
        if self.indirect_scores and (self.direct_score == 0 or self.best_indirect):
            best = self.best_indirect
            if best:
                result["related_entity_id"] = best["entity_id"]
                result["related_entity_text"] = best["entity_text"]

        return result


@observe(name="score_and_rank_collections")
def score_and_rank_collections(
    embedding_results: list[dict[str, Any]],
    similarity_threshold: float = 0.3,
) -> list[dict[str, Any]]:
    """
    Score and rank collections based on direct and indirect signals.

    This implements the discovery-first approach:
    1. Separate results by entity type
    2. For non-collection entities, look up associated collections
    3. Score each collection based on direct + indirect signals
    4. Rank by combined score

    Args:
        embedding_results: Results from search_all_entity_types()
        similarity_threshold: Minimum combined score to include

    Returns:
        List of collection records ranked by relevance, ready for CMR enrichment
    """
    # Dictionary to accumulate scores: collection_id -> CollectionScore
    scores: dict[str, CollectionScore] = {}

    # Separate direct collection matches from other entity types
    collection_matches = []
    other_matches = []

    for result in embedding_results:
        if result.get("type") == "collection":
            collection_matches.append(result)
        else:
            other_matches.append(result)

    # Process direct collection matches
    for result in collection_matches:
        cid = result["external_id"]
        if cid not in scores:
            scores[cid] = CollectionScore(collection_id=cid)

        # Use the highest direct score if multiple matches
        if result["similarity"] > scores[cid].direct_score:
            scores[cid].direct_score = result["similarity"]
            scores[cid].direct_attribute = result.get("attribute")
            scores[cid].direct_text = result.get("text_content")

    # Process indirect matches: look up associated collections
    if other_matches:
        entities = [(r["external_id"], r["type"]) for r in other_matches]
        collections_map = get_collections_for_entities(entities)

        # Add indirect signals
        for result in other_matches:
            entity_id = result["external_id"]
            entity_type = result["type"]
            entity_text = result.get("text_content", "")
            similarity = result.get("similarity", 0.0)

            # Get collections associated with this entity
            associated_collections = collections_map.get(entity_id, [])

            for cid in associated_collections:
                if cid not in scores:
                    scores[cid] = CollectionScore(collection_id=cid)

                scores[cid].add_indirect_signal(
                    entity_id=entity_id,
                    entity_type=entity_type,
                    entity_text=entity_text,
                    similarity=similarity,
                )

    # Compute combined scores
    for score in scores.values():
        score.compute_combined_score()

    # Filter by threshold and sort by combined score
    ranked = [s for s in scores.values() if s.combined_score >= similarity_threshold]
    ranked.sort(key=lambda s: s.combined_score, reverse=True)

    # Log summary
    direct_count = sum(1 for s in ranked if s.direct_score > 0)
    indirect_only = sum(1 for s in ranked if s.direct_score == 0 and s.indirect_scores)
    both_count = sum(1 for s in ranked if s.direct_score > 0 and s.indirect_scores)

    logger.info(
        "Scored %d collections: %d direct, %d indirect-only, %d both (threshold %.2f)",
        len(ranked),
        direct_count - both_count,
        indirect_only,
        both_count,
        similarity_threshold,
    )

    # Convert to embedding result format
    return [s.to_embedding_result() for s in ranked]


def explain_collection_ranking(score: CollectionScore) -> str:
    """
    Generate a human-readable explanation of why a collection ranked where it did.

    Useful for debugging and for explaining results to users.
    """
    parts = []

    if score.direct_score > 0:
        parts.append(f"Direct match (score: {score.direct_score:.2f})")

    if score.indirect_scores:
        parts.append(f"{len(score.indirect_scores)} indirect signal(s):")
        for signal in sorted(
            score.indirect_scores, key=lambda x: x["weighted_score"], reverse=True
        )[:3]:
            parts.append(
                f'  - {signal["entity_type"]}: "{signal["entity_text"][:50]}..." '
                f"(sim: {signal['similarity']:.2f}, weight: {signal['weight']:.1f})"
            )

    parts.append(f"Combined score: {score.combined_score:.2f}")

    return "\n".join(parts)
