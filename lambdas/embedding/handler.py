"""
Embedding Lambda - Processes CMR concept events from FIFO queue.

Flow:
1. Receive SQS message with concept-id and action (update/delete)
2. For updates: fetch metadata from CMR, extract text chunks, generate embeddings, store
3. For deletes: remove all stored embeddings and associations

Storage:
- embeddings: All embeddings (concept text chunks + KMS terms)
- associations: Links between entities (concept↔concept, concept↔KMS term)
"""

import json
import logging
from typing import Any

from pydantic import ValidationError

from util.cmr import CMRError, extract_data, fetch_associations, fetch_concept
from util.datastores import EmbeddingDatastore, get_datastore
from util.embeddings import EmbeddingError, EmbeddingGenerator, get_embedding_generator
from util.enrichment import enrich_collection_metadata
from util.kms import lookup_terms
from util.langfuse import flush_langfuse, get_langfuse
from util.models import CollectionData, ConceptMessage, EmbeddingChunk, KMSTerm
from util.spatial import extract_spatial_extent
from util.temporal import extract_temporal_extent

logging.getLogger().setLevel(logging.INFO)
logger = logging.getLogger(__name__)


def embed_chunks(
    chunks: list[EmbeddingChunk],
    embedder: EmbeddingGenerator,
    span: Any = None,
) -> list[tuple[str, str, list[float]]]:
    """
    Generate embeddings for text chunks.

    Returns list of (attribute, text_content, embedding) tuples ready for storage.
    """
    results = []
    for chunk in chunks:
        embedding = embedder.generate(
            chunk.text_content,
            concept_type=chunk.concept_type,
            attribute=chunk.attribute,
            span=span,
            metadata={
                "embedding_type": "cmr_concept",
                "concept_id": chunk.concept_id,
                "concept_type": chunk.concept_type.value,
                "attribute": chunk.attribute,
            },
        )
        results.append((chunk.attribute, chunk.text_content, embedding))
    return results


def process_kms_terms(
    kms_terms: list[KMSTerm],
    datastore: EmbeddingDatastore,
    embedder: EmbeddingGenerator,
    span: Any = None,
) -> list[tuple[str, str]]:
    """
    Look up KMS terms in the NASA keyword system, embed new ones, return refs.

    KMS terms (instruments, platforms, science keywords) are shared across many
    concepts - e.g., hundreds of collections reference "MODIS". We embed each
    unique term once and store it separately, then link concepts to terms via
    the associations table.

    Returns:
        List of (kms_uuid, scheme) tuples to link to the concept
    """
    # Dedupe terms first (e.g., same instrument listed twice)
    unique_terms = {}
    for ref in kms_terms:
        key = (ref.term, ref.scheme)
        if key not in unique_terms:
            unique_terms[key] = ref

    if not unique_terms:
        return []

    # Batch lookup all terms - KMS client handles scheme caching internally
    lookup_results = lookup_terms(list(unique_terms.keys()))

    # Log any terms that weren't found
    for key, kms_term in lookup_results.items():
        if kms_term is None:
            logger.debug("KMS term not found: %s/%s", key[1], key[0])

    # Process results: collect refs and embed any new terms
    kms_refs = []
    for kms_term in lookup_results.values():
        if kms_term is None:
            continue

        # If embedding already exists, add to associations list
        if datastore.get_kms_embedding(kms_term.uuid):
            kms_refs.append((kms_term.uuid, kms_term.scheme))
            continue

        # Embed the term with its definition for richer semantic matching
        text = f"{kms_term.term}: {kms_term.definition}" if kms_term.definition else kms_term.term

        try:
            embedding = embedder.generate(
                text,
                concept_type="kms_term",
                attribute=kms_term.scheme,
                span=span,
                metadata={
                    "embedding_type": "kms_term",
                    "kms_uuid": kms_term.uuid,
                    "kms_term": kms_term.term,
                    "kms_scheme": kms_term.scheme,
                },
            )
        except EmbeddingError as e:
            logger.warning("Failed to embed KMS term %s: %s", kms_term.term, e)
            continue

        inserted = datastore.upsert_kms_embedding(
            kms_uuid=kms_term.uuid,
            scheme=kms_term.scheme,
            term=kms_term.term,
            definition=kms_term.definition,
            embedding=embedding,
        )

        # Only add to associations if insert succeeded or another Lambda inserted it
        if inserted or datastore.get_kms_embedding(kms_term.uuid):
            kms_refs.append((kms_term.uuid, kms_term.scheme))

    return kms_refs


def handle_update(
    message: ConceptMessage,
    datastore: EmbeddingDatastore,
    embedder: EmbeddingGenerator,
    session_id: str | None = None,
) -> None:
    """
    Process a concept update: fetch metadata, extract text, generate embeddings, store.

    A concept (collection, variable, or citation) gets split into:
    1. Text chunks (title, abstract, etc.) - each embedded separately for precise matching
    2. KMS term links (instruments, platforms, keywords) - shared embeddings across concepts
    3. Associations (for collections: linked variables and citations)
    """
    langfuse = get_langfuse()

    if not langfuse:
        _handle_update_core(message, datastore, embedder, span=None)
        return

    trace_name = f"{message.concept_type.value}:{message.concept_id}"

    # pylint: disable=not-context-manager  # langfuse is guaranteed non-None after check above
    with langfuse.start_as_current_span(name=trace_name) as span:
        langfuse.update_current_trace(session_id=session_id)
        span.update(
            input={
                "concept_type": message.concept_type.value,
                "concept_id": message.concept_id,
                "revision_id": message.revision_id,
            }
        )

        result = _handle_update_core(message, datastore, embedder, span=span)

        span.update(output=result)


def _handle_update_core(
    message: ConceptMessage,
    datastore: EmbeddingDatastore,
    embedder: EmbeddingGenerator,
    span: Any = None,
) -> dict[str, int]:
    """Core update logic without tracing concerns."""
    metadata = fetch_concept(message.concept_id, message.revision_id)

    # For collections, upsert to collections table with enriched metadata
    if message.concept_type == "collection":
        temporal_start, temporal_end, is_ongoing = extract_temporal_extent(metadata)
        spatial_wkt, is_global = extract_spatial_extent(metadata)
        enriched = enrich_collection_metadata(metadata)

        collection_data = CollectionData(
            metadata=metadata,
            enriched_metadata=enriched,
            temporal_start=temporal_start,
            temporal_end=temporal_end,
            is_ongoing=is_ongoing,
            spatial_wkt=spatial_wkt,
            is_global=is_global,
        )
        datastore.upsert_collection(message.concept_id, collection_data)

    extraction = extract_data(message, metadata)
    logger.info(
        "Extracted %d chunks, %d KMS terms from %s",
        len(extraction.chunks),
        len(extraction.kms_terms),
        message.concept_id,
    )

    embedded = embed_chunks(extraction.chunks, embedder, span)
    datastore.upsert_chunks(message.concept_type, message.concept_id, embedded)

    # Process KMS terms (embed new ones) and link to this concept
    kms_refs = process_kms_terms(extraction.kms_terms, datastore, embedder, span)

    if kms_refs:
        datastore.upsert_kms_associations(message.concept_type, message.concept_id, kms_refs)

    # For collections, also store links to associated variables/citations
    if message.concept_type == "collection":
        associations = fetch_associations(message.concept_id)
        if associations:
            datastore.upsert_associations(message.concept_type, message.concept_id, associations)

    logger.info(
        "Processed %s: %d chunks, %d KMS terms", message.concept_id, len(embedded), len(kms_refs)
    )

    return {"chunks_stored": len(embedded), "kms_terms_linked": len(kms_refs)}


def handle_delete(message: ConceptMessage, datastore: EmbeddingDatastore) -> None:
    """Remove all stored data for a concept."""
    external_id = message.concept_id

    deleted_chunks = datastore.delete_chunks(external_id)
    deleted_assocs = datastore.delete_associations(external_id)
    deleted_kms = datastore.delete_kms_associations(external_id)

    # For collections, also delete from collections table
    deleted_collection = False
    if message.concept_type == "collection":
        deleted_collection = datastore.delete_collection(external_id)

    logger.info(
        "Deleted %s: %d chunks, %d associations, %d KMS links, collection=%s",
        external_id,
        deleted_chunks,
        deleted_assocs,
        deleted_kms,
        deleted_collection,
    )


def process_message(
    record: dict[str, Any],
    datastore: EmbeddingDatastore,
    embedder: EmbeddingGenerator,
) -> None:
    """Parse and route a single SQS message."""
    body = json.loads(record["body"])

    # Extract Langfuse session ID from message attributes if present
    session_id = record.get("messageAttributes", {}).get("LangfuseSessionId", {}).get("stringValue")

    message = ConceptMessage.model_validate(body)

    if message.action == "concept-update":
        handle_update(message, datastore, embedder, session_id)
    elif message.action == "concept-delete":
        handle_delete(message, datastore)


def handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    """
    Lambda handler for FIFO queue messages.

    Uses partial batch response - failed messages are returned for retry,
    successful messages are deleted from the queue.
    """
    records = event.get("Records", [])
    logger.info("Processing %d messages", len(records))

    datastore = get_datastore()
    embedder = get_embedding_generator()
    failures = []

    try:
        for record in records:
            message_id = record["messageId"]
            try:
                process_message(record, datastore, embedder)
            except (CMRError, EmbeddingError, ValidationError, json.JSONDecodeError) as e:
                logger.exception("Failed message %s: %s", message_id, e)
                failures.append({"itemIdentifier": message_id})
    finally:
        flush_langfuse()

    if failures:
        logger.warning("Completed with %d/%d failures", len(failures), len(records))

    return {"batchItemFailures": failures}
