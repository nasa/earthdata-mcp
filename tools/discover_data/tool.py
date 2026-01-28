"""
Discover Data orchestrator tool.

Main MCP tool for natural language discovery of NASA Earth science data collections.
Coordinates temporal/spatial extraction, semantic search, and disambiguation.

Uses a discovery-first approach: searches all entity types (collections, variables,
instruments, citations, science keywords) and ranks collections based on both
direct matches and indirect signals from related entities.
"""

import logging

from langfuse import get_client, observe

from tools.discover_data.input_model import (
    DiscoverDataInput,
    SearchContext,
    SpatialConstraint,
    TemporalConstraint,
)
from tools.discover_data.output_model import (
    CollectionMatch,
    DiscoverDataOutput,
    DiscoveryStatus,
    ExtractedConstraints,
)
from tools.discover_data.utils.collection_scoring import score_and_rank_collections
from tools.discover_data.utils.constraint_extraction import extract_constraints
from tools.discover_data.utils.disambiguation import (
    filter_by_user_refinements,
)
from tools.discover_data.utils.embedding_search import search_all_entity_types
from tools.discover_data.utils.query_expansion import (
    analyze_embedding_results,
    generate_expansion_questions,
    should_expand_query,
)

logger = logging.getLogger(__name__)

try:
    langfuse = get_client()
except Exception as e:
    logger.warning("Failed to initialize Langfuse client: %s", e)
    langfuse = None


@observe(name="discover_data")
def discover_data(query: DiscoverDataInput) -> dict:  # pylint: disable=too-many-branches
    """
    Discover NASA earth science data collections using natural language.

    This orchestrator uses a discovery-first approach:
    1. Extracts temporal and spatial constraints from the query
    2. Searches ALL entity types (collections, variables, instruments, etc.)
    3. Scores collections based on direct matches + indirect signals
    4. Applies any user refinements and checks for query expansion or disambiguation needs
    5. Returns ranked results with clarifying questions if needed

    Args:
        query: Natural language query with optional constraints and context

    Returns:
        Dictionary representation of DiscoverDataOutput
    """
    if langfuse:
        langfuse.update_current_trace(
            tags=["orchestrator", "discovery"],
            metadata={
                "query_length": len(query.query),
                "has_temporal_constraint": query.temporal_constraint is not None,
                "has_spatial_constraint": query.spatial_constraint is not None,
                "is_refinement": query.previous_context is not None,
                "max_results": query.max_results,
            },
        )

    try:
        # === PHASE 1: Constraint Extraction ===
        temporal, spatial = _extract_or_use_constraints(query)

        extracted = ExtractedConstraints(
            temporal_start=temporal.start_date,
            temporal_end=temporal.end_date,
            temporal_reasoning=temporal.reasoning,
            spatial_location=spatial.location,
            spatial_wkt=spatial.wkt_geometry,
        )

        # === PHASE 2: Discovery Search (All Entity Types) ===
        # Search collections, variables, instruments, citations, science keywords
        all_results = search_all_entity_types(
            query.query,
            similarity_threshold=0.3,  # Lower threshold, scoring will filter
            limit=50,  # Get more results for better scoring
        )

        if langfuse:
            # Log breakdown by type
            type_counts = {}
            for r in all_results:
                t = r["type"]
                type_counts[t] = type_counts.get(t, 0) + 1
            langfuse.update_current_trace(
                metadata={
                    "phase2_results_by_type": type_counts,
                    "phase2_total_results": len(all_results),
                },
            )

        # === PHASE 3: Collection Scoring & Ranking ===
        # Score collections based on direct + indirect signals
        ranked_collections = score_and_rank_collections(
            all_results,
            similarity_threshold=query.similarity_threshold,
        )

        if langfuse:
            langfuse.update_current_trace(
                metadata={
                    "phase3_ranked_collections": len(ranked_collections),
                },
            )

        # === PHASE 4: Transform to CollectionMatch Objects ===
        # Convert scored embedding results into CollectionMatch objects
        #
        # TODO: Once embedding results include pre-enriched metadata:
        # - Remove _transform_to_collection_matches helper
        # - Transform inline, populating CollectionMatch with enriched fields
        # - Enriched metadata will enable constraint filtering (Phase 5) and disambiguation (Phase 6)
        #
        # For now, using lightweight transformation without enriched metadata
        filtered_collections = _transform_to_collection_matches(ranked_collections)

        if langfuse:
            langfuse.update_current_trace(
                metadata={
                    "phase4_collection_matches": len(filtered_collections),
                },
            )

        # === PHASE 5: Apply Constraint Filtering ===
        # Filter collections that don't meet temporal/spatial constraints
        #
        # TODO: Once enriched metadata is available in Phase 4:
        # - Apply temporal/spatial constraint filtering
        # - Requires enriched metadata from embedding results
        #
        # For now, all collections pass through without filtering

        # Apply user refinements from previous context
        if query.previous_context and query.previous_context.user_refinements:
            filtered_collections = filter_by_user_refinements(
                filtered_collections,
                query.previous_context.user_refinements,
            )

        if langfuse:
            langfuse.update_current_trace(
                metadata={
                    "phase5_after_filtering": len(filtered_collections),
                },
            )

        # === PHASE 6: Query Expansion or Disambiguation ===
        questions = []

        if should_expand_query(filtered_collections, all_results, query.similarity_threshold):
            discovery_context = analyze_embedding_results(all_results)
            questions = generate_expansion_questions(query.query, discovery_context)
            status = DiscoveryStatus.REFINEMENT_SUGGESTED
            needs_disambiguation = False
        else:
            # Temporal resolution-based disambiguation
            #
            # TODO: Once enriched metadata is available in Phase 4:
            # - Extract metadata from CollectionMatch objects
            # - Check for temporal disambiguation needs
            # - Generate clarifying questions if needed
            #
            # collection_metas = [
            #     c.metadata
            #     for c in filtered_collections
            #     if getattr(c, "metadata", None) and isinstance(c.metadata, dict)
            # ]
            #
            # if collection_metas:
            #     needs_temporal_disambiguation, resolution_options = check_temporal_disambiguation(collection_metas)
            # else:
            #     needs_temporal_disambiguation, resolution_options = False, []
            # For now, skip temporal disambiguation since metadata is not available
            needs_temporal_disambiguation = False
            resolution_options = []

            # Convert resolution options to clarifying questions format
            questions = []
            if needs_temporal_disambiguation and resolution_options:
                questions = [
                    {
                        "question_id": "temporal_resolution",
                        "question_text": "Multiple temporal resolutions found. Which do you prefer?",
                        "question_type": "select",
                        "options": resolution_options,
                    }
                ]

            needs_disambiguation = needs_temporal_disambiguation
            status = _determine_status(
                filtered_collections,
                needs_disambiguation,
                ranked_collections,
            )

        # === PHASE 7: Output Assembly ===
        final_collections = filtered_collections[: query.max_results]

        search_context = _build_search_context(
            temporal, spatial, final_collections, query.previous_context
        )

        output = DiscoverDataOutput(
            status=status,
            collections=final_collections,
            total_found=len(filtered_collections),
            clarifying_questions=questions,
            extracted_constraints=extracted,
            search_context=search_context,
            error_message=None,
            search_strategy=_describe_search_strategy(temporal, spatial, ranked_collections),
        )

        if langfuse:
            langfuse.update_current_trace(
                tags=["success", status.value],
                metadata={
                    "final_collection_count": len(final_collections),
                    "total_found": len(filtered_collections),
                    "needs_disambiguation": needs_disambiguation,
                    "question_count": len(questions),
                },
            )

        return output.model_dump()

    except Exception as e:
        logger.exception("Error in discover_data")

        if langfuse:
            langfuse.update_current_trace(
                tags=["error"],
                metadata={
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
            )

        return DiscoverDataOutput(
            status=DiscoveryStatus.ERROR,
            error_message=str(e),
        ).model_dump()


def _extract_or_use_constraints(
    query: DiscoverDataInput,
) -> tuple[TemporalConstraint, SpatialConstraint]:
    """Extract constraints or use explicit ones from input."""
    # Check previous context first
    if query.previous_context:
        temporal = query.previous_context.temporal or query.temporal_constraint
        spatial = query.previous_context.spatial or query.spatial_constraint
        if temporal and spatial:
            return temporal, spatial

    # Extract from query
    return extract_constraints(
        query.query,
        explicit_temporal=query.temporal_constraint,
        explicit_spatial=query.spatial_constraint,
    )


def _transform_to_collection_matches(
    ranked_collections: list[dict],
) -> list[CollectionMatch]:
    """
    Transform scored embedding results into CollectionMatch objects.

    This is a lightweight transformation without CMR enrichment.

    Args:
        ranked_collections: Scored collection results from embedding search

    Returns:
        List of CollectionMatch objects (non-enriched)
    """
    matches = []

    for result in ranked_collections:
        # Only process collection results
        if result.get("type") != "collection":
            continue

        # Create minimal CollectionMatch from embedding result
        # Field mapping from embedding results:
        # - external_id -> concept_id
        # - text_content -> title
        # - attribute -> matched_attribute
        # - similarity -> similarity_score
        match = CollectionMatch(
            concept_id=result["external_id"],
            title=result.get("text_content", ""),
            short_name="",  # Not available in embedding results
            score=result.get("score", 0.0),
            match_type=result.get("match_type", "direct"),
            similarity_score=result.get("similarity", 0.0),
            matched_attribute=result.get("attribute"),
            related_entity_id=result.get("related_entity_id"),
            related_entity_text=result.get("related_entity_text"),
            metadata=result.get("metadata"),  # Pass through any metadata we have
        )
        matches.append(match)

    return matches


def _determine_status(
    filtered_collections: list[CollectionMatch],
    needs_disambiguation: bool,
    ranked_results: list[dict],
) -> DiscoveryStatus:
    """Determine the appropriate discovery status."""
    if not filtered_collections and not ranked_results:
        return DiscoveryStatus.NO_RESULTS

    if needs_disambiguation:
        return DiscoveryStatus.DISAMBIGUATION_NEEDED

    # Check if any results are indirect matches
    has_indirect = any(
        c.match_type not in ("direct", "direct_and_indirect") for c in filtered_collections
    )
    if has_indirect:
        return DiscoveryStatus.INDIRECT_MATCHES

    return DiscoveryStatus.COLLECTIONS_FOUND


def _build_search_context(
    temporal: TemporalConstraint,
    spatial: SpatialConstraint,
    collections: list[CollectionMatch],
    previous_context: SearchContext | None,
) -> dict:
    """Build search context for follow-up queries."""
    iteration = (previous_context.search_iteration + 1) if previous_context else 1
    refinements = previous_context.user_refinements if previous_context else {}

    context = SearchContext(
        temporal=temporal,
        spatial=spatial,
        previous_collection_ids=[c.concept_id for c in collections],
        user_refinements=refinements,
        search_iteration=iteration,
    )

    return context.model_dump()


def _describe_search_strategy(
    temporal: TemporalConstraint,
    spatial: SpatialConstraint,
    ranked_collections: list[dict],
) -> str:
    """Generate a human-readable description of the search strategy."""
    parts = ["Discovery search across all entity types"]

    # Count match types
    direct_count = sum(1 for r in ranked_collections if r.get("match_type") == "direct")
    indirect_count = sum(
        1 for r in ranked_collections if r.get("match_type", "").startswith("via_")
    )
    both_count = sum(1 for r in ranked_collections if r.get("match_type") == "direct_and_indirect")

    if direct_count or both_count:
        parts.append(f"{direct_count + both_count} direct collection matches")

    if indirect_count or both_count:
        parts.append(f"{indirect_count + both_count} collections found via related entities")

    if temporal.start_date or temporal.end_date:
        parts.append("with temporal filtering")

    if spatial.wkt_geometry:
        parts.append("with spatial filtering")

    return ", ".join(parts)
