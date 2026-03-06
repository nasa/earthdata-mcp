"""
Discover Data orchestrator tool.

Main MCP tool for natural language discovery of NASA Earth science data collections.
Coordinates temporal/spatial extraction, semantic search, and disambiguation.

Uses a discovery-first approach: searches all entity types (collections, variables,
instruments, citations, science keywords) and ranks collections based on both
direct matches and indirect signals from related entities.
"""

import logging

from langfuse import observe

from models.tools.discover_data import (
    CollectionMatch,
    DiscoverDataInput,
    DiscoverDataOutput,
    DiscoveryStatus,
    ExtractedConstraints,
    SearchContext,
    SpatialConstraint,
    TemporalConstraint,
)
from util.langfuse import trace_update

from .utils.collection_hydration import hydrate_collections
from .utils.collection_scoring import score_and_rank_collections
from .utils.constraint_extraction import extract_constraints
from .utils.disambiguation import (
    check_disambiguation,
    filter_by_user_refinements,
)
from .utils.embedding_search import search_all_entity_types
from .utils.granule_availability import (
    GranuleValidationError,
    validate_granule_availability,
)
from .utils.query_expansion import (
    analyze_embedding_results,
    generate_expansion_questions,
    should_expand_query,
)
from .utils.tool_associations import (
    ToolAssociationError,
    enrich_with_tool_associations,
)

logger = logging.getLogger(__name__)


@observe(name="discover_data")
def discover_data(params: DiscoverDataInput) -> dict:  # pylint: disable=too-many-branches
    """
    Discover NASA earth science data collections using natural language.

    This orchestrator uses a discovery-first approach:
    1. PHASE 1: Extracts temporal and spatial constraints from the query
    2. PHASE 2: Searches ALL entity types (collections, variables, instruments, etc.)
    3. PHASE 3: Scores collections based on direct matches + indirect signals
    4. PHASE 4: Hydrates collections and applies temporal/spatial filtering
    5. PHASE 5: Validates granule availability for filtered collections
    6. PHASE 6: Enriches collections with UMM-T tool associations
    7. PHASE 7: Applies user refinements and checks for query expansion or disambiguation
    8. PHASE 8: Returns ranked results with clarifying questions if needed

    Args:
        params: Natural language query with optional constraints and context

    Returns:
        Dictionary representation of DiscoverDataOutput
    """
    trace_update(
        tags=["orchestrator", "discovery"],
        metadata={
            "query_length": len(params.query),
            "has_search_context": params.search_context is not None,
            "has_temporal_in_context": (
                params.search_context is not None and params.search_context.temporal is not None
            ),
            "has_spatial_in_context": (
                params.search_context is not None and params.search_context.spatial is not None
            ),
            "max_results": params.max_results,
        },
    )

    try:
        # === PHASE 1: Constraint Extraction ===
        # Extract temporal and spatial constraints from query
        temporal, spatial = _extract_or_use_constraints(params)

        extracted = ExtractedConstraints(
            temporal_start=temporal.start_date,
            temporal_end=temporal.end_date,
            temporal_reasoning=temporal.reasoning,
            spatial_location=spatial.location,
            spatial_wkt=spatial.wkt_geometry,
        )

        # === PHASE 2: Discovery Search (All Entity Types) ===
        embedding_results = search_all_entity_types(
            params.query,
            similarity_threshold=0.3,  # Lower threshold, scoring will filter
            limit=50,  # Get more candidates for better scoring
        )

        type_counts = {}
        for r in embedding_results:
            t = r["type"]
            type_counts[t] = type_counts.get(t, 0) + 1

        trace_update(
            metadata={
                "embedding_results_by_type": type_counts,
                "embedding_results_count": len(embedding_results),
            },
        )

        # === PHASE 3: Collection Scoring & Ranking ===
        scored_collections = score_and_rank_collections(
            embedding_results,
            similarity_threshold=params.similarity_threshold,
        )

        trace_update(metadata={"scored_collections_count": len(scored_collections)})

        # === PHASE 4: Hydration & Filtering ===
        collections = hydrate_collections(
            scored_collections,
            temporal_start=temporal.start_date,
            temporal_end=temporal.end_date,
            spatial_wkt=spatial.wkt_geometry,
        )

        trace_update(metadata={"hydrated_collections_count": len(collections)})

        # === PHASE 5: Granule Validation ===
        collections_before_granule_validation = len(collections)

        collections = validate_granule_availability(
            collections,
            temporal.start_date,
            temporal.end_date,
            spatial.wkt_geometry,
        )

        all_filtered_by_granule_validation = (
            collections_before_granule_validation > 0 and not collections
        )

        if collections_before_granule_validation != len(collections):
            trace_update(
                metadata={
                    "collections_before_granule_validation": collections_before_granule_validation,
                    "collections_after_granule_validation": len(collections),
                    "filtered_by_granule_check": (
                        collections_before_granule_validation - len(collections)
                    ),
                }
            )

        # === PHASE 6: Tool Association Enrichment ===
        if not all_filtered_by_granule_validation:
            collections = enrich_with_tool_associations(
                collections,
                temporal=temporal,
                spatial=spatial,
            )

        # Apply user refinements from search context (disambiguation answers)
        if params.search_context and params.search_context.user_refinements:
            collections = filter_by_user_refinements(
                collections,
                params.search_context.user_refinements,
            )

            trace_update(metadata={"after_refinements_count": len(collections)})

        # === PHASE 7: Query Expansion or Disambiguation ===
        questions = []
        needs_disambiguation = False

        if should_expand_query(collections, embedding_results, params.similarity_threshold):
            discovery_context = analyze_embedding_results(embedding_results)
            questions = generate_expansion_questions(params.query, discovery_context)
            status = DiscoveryStatus.REFINEMENT_SUGGESTED
        else:
            needs_disambiguation, questions = check_disambiguation(collections)

            status = _determine_status(
                collections,
                needs_disambiguation,
                scored_collections,
                all_filtered_by_granule_validation=all_filtered_by_granule_validation,
            )

        # === PHASE 8: Output Assembly ===
        final_collections = collections[: params.max_results]

        search_context = _build_search_context(
            temporal, spatial, final_collections, params.search_context
        )

        output = DiscoverDataOutput(
            status=status,
            collections=final_collections,
            total_found=len(collections),
            clarifying_questions=questions,
            extracted_constraints=extracted,
            search_context=search_context,
            error_message=None,
            search_strategy=_describe_search_strategy(temporal, spatial, scored_collections),
        )

        trace_update(
            tags=["success", status.value],
            metadata={
                "returned_count": len(final_collections),
                "total_matches": len(collections),
                "question_count": len(questions),
            },
        )

        return output.model_dump()

    except GranuleValidationError:
        logger.warning("Granule availability check failed", exc_info=True)

        trace_update(
            tags=["error"],
            metadata={"error_type": "GranuleValidationError"},
        )

        return DiscoverDataOutput(
            status=DiscoveryStatus.ERROR,
            error_message=(
                "Granule availability check failed due to a service error. "
                "Please try your request again."
            ),
        ).model_dump()

    except ToolAssociationError:
        logger.warning("Tool association enrichment failed", exc_info=True)

        trace_update(
            tags=["error"],
            metadata={"error_type": "ToolAssociationError"},
        )

        return DiscoverDataOutput(
            status=DiscoveryStatus.ERROR,
            error_message=(
                "Tool association enrichment failed due to a service error. "
                "Please try your request again."
            ),
        ).model_dump()

    except Exception as e:
        logger.exception("Error in discover_data: %s", e)

        trace_update(
            tags=["error"],
            metadata={
                "error_type": type(e).__name__,
                "error_message": str(e),
            },
        )

        return DiscoverDataOutput(
            status=DiscoveryStatus.ERROR,
            error_message="An unexpected error occurred. Please try your request again.",
        ).model_dump()


def _extract_or_use_constraints(
    query: DiscoverDataInput,
) -> tuple[TemporalConstraint, SpatialConstraint]:
    """Extract constraints or use prior ones from input."""
    # Prefer prior constraints from search_context to avoid re-extraction
    if query.search_context and query.search_context.temporal and query.search_context.spatial:
        return query.search_context.temporal, query.search_context.spatial

    # Extract from query
    temporal, spatial = extract_constraints(
        query.query,
        prior_temporal=None,
        prior_spatial=None,
    )

    return temporal, spatial


def _determine_status(
    collections: list[CollectionMatch],
    needs_disambiguation: bool,
    _ranked_results: list[dict],
    all_filtered_by_granule_validation: bool = False,
) -> DiscoveryStatus:
    """Determine the appropriate discovery status."""
    if all_filtered_by_granule_validation:
        return DiscoveryStatus.NO_GRANULES_IN_CONSTRAINTS

    if not collections:
        return DiscoveryStatus.NO_RESULTS

    if needs_disambiguation:
        return DiscoveryStatus.DISAMBIGUATION_NEEDED

    # Check if any results are indirect matches
    has_indirect = any(c.match_type not in ("direct", "direct_and_indirect") for c in collections)
    if has_indirect:
        return DiscoveryStatus.INDIRECT_MATCHES

    return DiscoveryStatus.COLLECTIONS_FOUND


def _build_search_context(
    temporal: TemporalConstraint,
    spatial: SpatialConstraint,
    collections: list[CollectionMatch],
    prior_context: SearchContext | None,
) -> SearchContext:
    """Build search context for follow-up queries."""
    iteration = (prior_context.search_iteration + 1) if prior_context else 1
    refinements = prior_context.user_refinements if prior_context else {}

    return SearchContext(
        temporal=temporal,
        spatial=spatial,
        previous_collection_ids=[c.concept_id for c in collections],
        user_refinements=refinements,
        search_iteration=iteration,
    )


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
