"""
Embedding Lambda - Processes CMR concept events from FIFO queue.

Flow:
1. Receive SQS message with concept-id and action (update/delete)
2. For updates: fetch metadata from CMR, extract text chunks, generate embeddings, store
3. For deletes: remove all stored embeddings and associations

Storage:
- concept_embeddings: Text chunks (title, abstract, etc.) with their embeddings
- kms_embeddings: Shared vocabulary terms (instruments, platforms) with embeddings
- concept_kms_associations: Links concepts to KMS terms they reference
"""

import json
import logging
from typing import Any

from pydantic import ValidationError

from util.cmr import CMRError, extract_data, fetch_associations, fetch_concept
from util.datastores import EmbeddingDatastore, get_datastore
from util.embeddings import EmbeddingError, EmbeddingGenerator, get_embedding_generator
from util.kms import lookup_term
from util.langfuse import flush_langfuse, get_langfuse
from util.models import ConceptMessage, EmbeddingChunk, KMSTerm

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ProcessingError(Exception):
    """Raised when processing a concept fails."""


def embed_chunks(
    chunks: list[EmbeddingChunk],
    embedder: EmbeddingGenerator,
    trace: Any = None,
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
            trace=trace,
        )
        results.append((chunk.attribute, chunk.text_content, embedding))
    return results


def process_kms_terms(
    kms_terms: list[KMSTerm],
    datastore: EmbeddingDatastore,
    embedder: EmbeddingGenerator,
    trace: Any = None,
) -> list[str]:
    """
    Look up KMS terms in the NASA keyword system, embed new ones, return UUIDs.

    KMS terms (instruments, platforms, science keywords) are shared across many
    concepts - e.g., hundreds of collections reference "MODIS". We embed each
    unique term once and store it separately, then link concepts to terms via
    the concept_kms_associations table.

    Returns:
        List of KMS UUIDs to link to the concept
    """
    uuids = []
    seen = set()

    for ref in kms_terms:
        # Skip duplicates within this batch (e.g., same instrument listed twice)
        key = (ref.term, ref.scheme)
        if key in seen:
            continue
        seen.add(key)

        # Look up term in KMS API to get UUID and definition
        kms_term = lookup_term(ref.term, ref.scheme)
        if not kms_term:
            logger.debug("KMS term not found: %s/%s", ref.scheme, ref.term)
            continue

        uuids.append(kms_term.uuid)

        # Skip embedding if we already have this term stored
        if datastore.get_kms_embedding(kms_term.uuid):
            continue

        # Embed the term with its definition for richer semantic matching
        text = f"{kms_term.term}: {kms_term.definition}" if kms_term.definition else kms_term.term

        try:
            embedding = embedder.generate(
                text, concept_type="kms", attribute=ref.scheme, trace=trace
            )
        except EmbeddingError as e:
            logger.warning("Failed to embed KMS term %s: %s", kms_term.term, e)
            continue

        datastore.upsert_kms_embedding(
            kms_uuid=kms_term.uuid,
            scheme=kms_term.scheme,
            term=kms_term.term,
            definition=kms_term.definition,
            embedding=embedding,
        )

    return uuids


def handle_update(
    message: ConceptMessage,
    datastore: EmbeddingDatastore,
    embedder: EmbeddingGenerator,
) -> None:
    """
    Process a concept update: fetch metadata, extract text, generate embeddings, store.

    A concept (collection, variable, or citation) gets split into:
    1. Text chunks (title, abstract, etc.) - each embedded separately for precise matching
    2. KMS term links (instruments, platforms, keywords) - shared embeddings across concepts
    3. Associations (for collections: linked variables and citations)
    """
    langfuse = get_langfuse()
    trace = None
    if langfuse:
        trace = langfuse.trace(  # pylint: disable=no-member
            name="process-concept-update",
            metadata={
                "concept_type": message.concept_type,
                "concept_id": message.concept_id,
                "revision_id": message.revision_id,
            },
        )

    # Fetch full metadata from CMR
    try:
        metadata = fetch_concept(message.concept_id, message.revision_id)
    except CMRError as e:
        raise ProcessingError(f"Failed to fetch {message.concept_id}: {e}") from e

    # Extract text fields and KMS term references from the metadata
    extraction = extract_data(message, metadata)
    logger.info(
        "Extracted %d chunks, %d KMS terms from %s",
        len(extraction.chunks),
        len(extraction.kms_terms),
        message.concept_id,
    )

    # Generate embeddings for each text chunk and store
    try:
        embedded = embed_chunks(extraction.chunks, embedder, trace)
    except EmbeddingError as e:
        raise ProcessingError(f"Embedding failed for {message.concept_id}: {e}") from e

    datastore.upsert_chunks(message.concept_type, message.concept_id, embedded)

    # Process KMS terms (embed new ones) and link to this concept
    kms_uuids = process_kms_terms(extraction.kms_terms, datastore, embedder, trace)
    if kms_uuids:
        datastore.upsert_concept_kms_associations(
            message.concept_type, message.concept_id, kms_uuids
        )

    # For collections, also store links to associated variables/citations
    if message.concept_type == "collection":
        associations = fetch_associations(message.concept_id)
        if associations:
            datastore.upsert_associations(message.concept_type, message.concept_id, associations)

    if trace:
        trace.update(
            output={
                "chunks_stored": len(embedded),
                "kms_terms_linked": len(kms_uuids),
            }
        )

    logger.info(
        "Processed %s: %d chunks, %d KMS terms", message.concept_id, len(embedded), len(kms_uuids)
    )


def handle_delete(message: ConceptMessage, datastore: EmbeddingDatastore) -> None:
    """Remove all stored data for a concept."""
    concept_id = message.concept_id

    deleted_chunks = datastore.delete_chunks(concept_id)
    deleted_assocs = datastore.delete_associations(concept_id)
    deleted_kms = datastore.delete_concept_kms_associations(concept_id)

    logger.info(
        "Deleted %s: %d chunks, %d associations, %d KMS links",
        concept_id,
        deleted_chunks,
        deleted_assocs,
        deleted_kms,
    )


def process_message(
    record: dict[str, Any],
    datastore: EmbeddingDatastore,
    embedder: EmbeddingGenerator,
) -> None:
    """Parse and route a single SQS message."""
    body = json.loads(record["body"])

    try:
        message = ConceptMessage.model_validate(body)
    except ValidationError as e:
        raise ProcessingError(f"Invalid message format: {e}") from e

    if message.action == "concept-update":
        handle_update(message, datastore, embedder)
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
            except (ProcessingError, Exception) as e:
                logger.error("Failed %s: %s", message_id, e)
                failures.append({"itemIdentifier": message_id})
    finally:
        datastore.close()
        flush_langfuse()

    if failures:
        logger.warning("Completed with %d/%d failures", len(failures), len(records))

    return {"batchItemFailures": failures}
