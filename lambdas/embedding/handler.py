"""
Embedding Lambda - FIFO queue consumer that processes CMR concept events.

Creates chunked embeddings by attribute for RAG retrieval, stored via
the configured repository backend. Supports multiple concept types:
- collection: title, abstract, purpose (concept_embeddings) + science_keywords, platforms, instruments (kms_embeddings)
- variable: name, long_name, definition (concept_embeddings) + science_keywords (kms_embeddings)
- citation: title, creator, publisher, other_citation_details (concept_embeddings)

KMS-sourced attributes (science_keywords, platforms, instruments) are stored in a
normalized kms_embeddings table and linked via concept_kms_associations.
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from util.cmr import CMRError, fetch_associations, fetch_concept
from util.datastores import get_datastore
from util.embeddings import EmbeddingError, get_embedding_generator
from util.kms import lookup_term
from util.langfuse import flush_langfuse, get_langfuse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ProcessingError(Exception):
    """Raised when processing a concept fails."""


@dataclass
class EmbeddingChunk:
    """
    Represents a single piece of text extracted from a CMR concept for embedding.

    Instead of embedding an entire concept as one vector, we split it into
    multiple chunks by attribute (title, abstract, keywords, etc.). This allows:
    - More precise similarity matching (match on abstract vs title)
    - Better RAG retrieval (return the specific relevant text)
    - Attribute-specific embedding models (see below)

    Example: A collection with title "MODIS Sea Surface Temperature" and
    abstract "Daily SST measurements..." becomes two EmbeddingChunks:
      - EmbeddingChunk(concept_type="collection", concept_id="C123", attribute="title", text_content="MODIS...")
      - EmbeddingChunk(concept_type="collection", concept_id="C123", attribute="abstract", text_content="Daily SST...")

    To use different embedding models per concept type or attribute, configure
    a RoutingEmbeddingGenerator in util/embeddings/__init__.py:

        from util.embeddings import RoutingEmbeddingGenerator, BedrockEmbeddingGenerator

        def get_embedding_generator():
            return RoutingEmbeddingGenerator({
                "collection.abstract": BedrockEmbeddingGenerator(model_id="amazon.titan-embed-text-v2:0"),
                "variable": SomeOtherGenerator(),  # Different model for variables
                "default": BedrockEmbeddingGenerator(),
            })

    The router checks keys in order: "{concept_type}.{attribute}" -> "{concept_type}" -> "default"
    """

    concept_type: str  # collection, variable, or citation
    concept_id: str  # CMR concept ID (e.g., C1234567-PROVIDER)
    attribute: str  # Which field this came from (title, abstract, etc.)
    text_content: str  # The actual text to embed


@dataclass
class KMSTermRef:
    """Reference to a KMS term to be looked up and associated with a concept."""

    term: str  # The term to look up (e.g., "MODIS", "TERRA", "PRECIPITATION")
    scheme: str  # KMS scheme (platforms, instruments, sciencekeywords)


@dataclass
class ExtractionResult:
    """Result of extracting data from a CMR concept."""

    chunks: list[EmbeddingChunk] = field(default_factory=list)
    kms_terms: list[KMSTermRef] = field(default_factory=list)


def extract_collection_data(
    concept_type: str,
    concept_id: str,
    collection: dict[str, Any],
) -> ExtractionResult:
    """
    Extract embeddable data from a CMR collection's UMM-C metadata.

    Returns:
    - Concept-specific chunks (title, abstract, purpose) -> stored in concept_embeddings
    - KMS term references (science_keywords, platforms, instruments) -> stored in kms_embeddings

    Args:
        concept_type: Always "collection" for this function
        concept_id: CMR concept ID (e.g., "C1234567890-PROVIDER")
        collection: UMM-C JSON metadata from CMR

    Returns:
        ExtractionResult with chunks and kms_terms
    """
    result = ExtractionResult()

    # Title (concept-specific)
    if title := collection.get("EntryTitle"):
        result.chunks.append(
            EmbeddingChunk(
                concept_type=concept_type,
                concept_id=concept_id,
                attribute="title",
                text_content=title,
            )
        )

    # Abstract (concept-specific)
    if abstract := collection.get("Abstract"):
        result.chunks.append(
            EmbeddingChunk(
                concept_type=concept_type,
                concept_id=concept_id,
                attribute="abstract",
                text_content=abstract,
            )
        )

    # Purpose (concept-specific)
    if purpose := collection.get("Purpose"):
        result.chunks.append(
            EmbeddingChunk(
                concept_type=concept_type,
                concept_id=concept_id,
                attribute="purpose",
                text_content=purpose,
            )
        )

    # Science keywords (KMS-sourced) - extract the most specific term
    if science_keywords := collection.get("ScienceKeywords"):
        for kw in science_keywords:
            # Get the most specific term in the hierarchy
            term = (
                kw.get("VariableLevel3")
                or kw.get("VariableLevel2")
                or kw.get("VariableLevel1")
                or kw.get("Term")
            )
            if term:
                result.kms_terms.append(KMSTermRef(term=term, scheme="sciencekeywords"))

    # Platforms (KMS-sourced)
    if platforms := collection.get("Platforms"):
        for platform in platforms:
            if platform_name := platform.get("ShortName"):
                result.kms_terms.append(KMSTermRef(term=platform_name, scheme="platforms"))

            # Instruments (KMS-sourced)
            for instrument in platform.get("Instruments", []):
                if instrument_name := instrument.get("ShortName"):
                    result.kms_terms.append(KMSTermRef(term=instrument_name, scheme="instruments"))

    return result


def extract_variable_data(
    concept_type: str,
    concept_id: str,
    variable: dict[str, Any],
) -> ExtractionResult:
    """
    Extract embeddable data from a CMR variable's UMM-Var metadata.

    Variables represent specific data fields within collections (e.g., sea_surface_temp).
    """
    result = ExtractionResult()

    # Name (concept-specific)
    if name := variable.get("Name"):
        result.chunks.append(
            EmbeddingChunk(
                concept_type=concept_type,
                concept_id=concept_id,
                attribute="name",
                text_content=name,
            )
        )

    # Long Name (concept-specific)
    if long_name := variable.get("LongName"):
        result.chunks.append(
            EmbeddingChunk(
                concept_type=concept_type,
                concept_id=concept_id,
                attribute="long_name",
                text_content=long_name,
            )
        )

    # Definition (concept-specific)
    if definition := variable.get("Definition"):
        result.chunks.append(
            EmbeddingChunk(
                concept_type=concept_type,
                concept_id=concept_id,
                attribute="definition",
                text_content=definition,
            )
        )

    # Science keywords (KMS-sourced) - extract the most specific term
    if science_keywords := variable.get("ScienceKeywords"):
        for kw in science_keywords:
            term = (
                kw.get("VariableLevel3")
                or kw.get("VariableLevel2")
                or kw.get("VariableLevel1")
                or kw.get("Term")
            )
            if term:
                result.kms_terms.append(KMSTermRef(term=term, scheme="sciencekeywords"))

    return result


def extract_citation_data(
    concept_type: str,
    concept_id: str,
    citation: dict[str, Any],
) -> ExtractionResult:
    """
    Extract embeddable data from a CMR citation.

    Citations reference publications/DOIs associated with collections.
    Citations don't have KMS-sourced terms, only concept-specific chunks.
    """
    result = ExtractionResult()
    metadata = citation.get("CitationMetadata", {})

    # Name (publication title)
    if name := citation.get("Name"):
        result.chunks.append(
            EmbeddingChunk(
                concept_type=concept_type,
                concept_id=concept_id,
                attribute="name",
                text_content=name,
            )
        )

    # Authors from CitationMetadata
    if authors := metadata.get("Author"):
        author_names = []
        for author in authors:
            given = author.get("Given", "")
            family = author.get("Family", "")
            if given and family:
                author_names.append(f"{given} {family}")
            elif family:
                author_names.append(family)
        if author_names:
            result.chunks.append(
                EmbeddingChunk(
                    concept_type=concept_type,
                    concept_id=concept_id,
                    attribute="authors",
                    text_content="; ".join(author_names),
                )
            )

    # Publisher from CitationMetadata
    if publisher := metadata.get("Publisher"):
        result.chunks.append(
            EmbeddingChunk(
                concept_type=concept_type,
                concept_id=concept_id,
                attribute="publisher",
                text_content=publisher,
            )
        )

    # Abstract
    if abstract := citation.get("Abstract"):
        result.chunks.append(
            EmbeddingChunk(
                concept_type=concept_type,
                concept_id=concept_id,
                attribute="abstract",
                text_content=abstract,
            )
        )

    return result


def extract_data(
    concept_type: str,
    concept_id: str,
    concept_data: dict[str, Any],
) -> ExtractionResult:
    """
    Route to the appropriate extractor based on concept type.

    CMR has different concept types (collection, variable, citation),
    each with different metadata schemas (UMM-C, UMM-Var, etc.).

    Returns:
        ExtractionResult containing:
        - chunks: Concept-specific text to embed (title, abstract, etc.)
        - kms_terms: KMS term references to look up and associate
    """
    extractors = {
        "collection": extract_collection_data,
        "variable": extract_variable_data,
        "citation": extract_citation_data,
    }

    extractor = extractors.get(concept_type)
    if not extractor:
        logger.warning("Unknown concept type: %s, skipping", concept_type)
        return ExtractionResult()

    return extractor(concept_type, concept_id, concept_data)


def process_kms_terms(
    kms_terms: list[KMSTermRef],
    datastore,
    embedder,
    trace=None,
) -> list[str]:
    """
    Process KMS terms: look up in KMS, embed if needed, return UUIDs.

    For each term:
    1. Look up in KMS to get uuid and definition
    2. Check if already in kms_embeddings table
    3. If not, generate embedding and store
    4. Return list of UUIDs for association

    Args:
        kms_terms: List of KMS term references to process
        datastore: Datastore instance
        embedder: Embedding generator
        trace: Optional Langfuse trace

    Returns:
        List of KMS UUIDs that were found/stored
    """
    kms_uuids = []
    seen = set()  # Deduplicate terms

    for term_ref in kms_terms:
        # Deduplicate by (term, scheme)
        key = (term_ref.term, term_ref.scheme)
        if key in seen:
            continue
        seen.add(key)

        # Look up in KMS
        kms_term = lookup_term(term_ref.term, term_ref.scheme)
        if not kms_term:
            logger.debug("KMS term not found: %s/%s", term_ref.scheme, term_ref.term)
            continue

        kms_uuids.append(kms_term.uuid)

        # Check if already in database
        existing = datastore.get_kms_embedding(kms_term.uuid)
        if existing:
            logger.debug("KMS embedding exists: %s/%s", term_ref.scheme, term_ref.term)
            continue

        # Generate embedding for new KMS term
        text_to_embed = (
            f"{kms_term.term}: {kms_term.definition}" if kms_term.definition else kms_term.term
        )

        try:
            embedding = embedder.generate(
                text_to_embed,
                concept_type="kms",
                attribute=term_ref.scheme,
                trace=trace,
            )
        except EmbeddingError as e:
            logger.warning("Failed to embed KMS term %s: %s", kms_term.term, e)
            continue

        # Store in kms_embeddings
        datastore.upsert_kms_embedding(
            kms_uuid=kms_term.uuid,
            scheme=kms_term.scheme,
            term=kms_term.term,
            definition=kms_term.definition,
            embedding=embedding,
        )

    return kms_uuids


def process_concept_update(message: dict[str, Any], datastore, embedder) -> None:
    """Process a concept update: fetch, extract, embed, store."""
    concept_type = message["concept-type"]
    concept_id = message["concept-id"]
    revision_id = str(message["revision-id"])

    logger.info(
        "Processing update for %s:%s (revision %s)",
        concept_type,
        concept_id,
        revision_id,
    )

    langfuse = get_langfuse()
    trace = None
    if langfuse:
        trace = langfuse.trace(
            name="process-concept-update",
            metadata={
                "concept_type": concept_type,
                "concept_id": concept_id,
                "revision_id": revision_id,
            },
        )

    try:
        concept_data = fetch_concept(concept_id, revision_id)
    except CMRError as e:
        raise ProcessingError(str(e)) from e

    # Extract both concept-specific chunks and KMS term references
    extraction = extract_data(concept_type, concept_id, concept_data)
    logger.info(
        "Extracted %d chunks and %d KMS terms for %s",
        len(extraction.chunks),
        len(extraction.kms_terms),
        concept_id,
    )

    # Process concept-specific chunks -> concept_embeddings
    embedded_chunks = []
    for chunk in extraction.chunks:
        try:
            embedding = embedder.generate(
                chunk.text_content,
                concept_type=chunk.concept_type,
                attribute=chunk.attribute,
                trace=trace,
            )
            embedded_chunks.append((chunk.attribute, chunk.text_content, embedding))
        except EmbeddingError as e:
            raise ProcessingError(str(e)) from e

    datastore.upsert_chunks(concept_type, concept_id, embedded_chunks)

    # Process KMS terms -> kms_embeddings + associations
    kms_uuids = process_kms_terms(extraction.kms_terms, datastore, embedder, trace)
    if kms_uuids:
        datastore.upsert_concept_kms_associations(concept_type, concept_id, kms_uuids)
        logger.info("Linked %d KMS terms to %s", len(kms_uuids), concept_id)

    # Store CMR associations for collections (variables, citations)
    if concept_type == "collection":
        associations = fetch_associations(concept_id)
        if associations:
            assoc_count = datastore.upsert_associations(concept_type, concept_id, associations)
            logger.info("Stored %d CMR associations for %s", assoc_count, concept_id)

    if trace:
        trace.update(
            output={
                "chunks_processed": len(embedded_chunks),
                "kms_terms_linked": len(kms_uuids),
                "attributes": [attr for attr, _, _ in embedded_chunks],
            }
        )

    logger.info(
        "Successfully processed %s: %d chunks, %d KMS terms",
        concept_id,
        len(embedded_chunks),
        len(kms_uuids),
    )


def process_concept_delete(message: dict[str, Any], datastore) -> None:
    """Process a concept delete: remove all chunks and associations from storage."""
    concept_id = message["concept-id"]
    logger.info("Processing delete for %s", concept_id)

    deleted_chunks = datastore.delete_chunks(concept_id)
    deleted_assocs = datastore.delete_associations(concept_id)
    deleted_kms_assocs = datastore.delete_concept_kms_associations(concept_id)

    if deleted_chunks:
        logger.info("Deleted %d chunks for %s", deleted_chunks, concept_id)
    if deleted_assocs:
        logger.info("Deleted %d CMR associations for %s", deleted_assocs, concept_id)
    if deleted_kms_assocs:
        logger.info("Deleted %d KMS associations for %s", deleted_kms_assocs, concept_id)
    if not deleted_chunks and not deleted_assocs and not deleted_kms_assocs:
        logger.warning("No chunks or associations found for %s", concept_id)


def process_message(record: dict[str, Any], datastore, embedder) -> None:
    """Process a single SQS message."""
    message = json.loads(record["body"])
    action = message.get("action")

    if action == "concept-update":
        process_concept_update(message, datastore, embedder)
    elif action == "concept-delete":
        process_concept_delete(message, datastore)
    else:
        logger.warning("Unknown action: %s", action)


def handler(event: dict[str, Any], context) -> dict[str, Any]:
    """
    Lambda handler for processing concept events from FIFO queue.

    Uses partial batch response for individual message failure handling.
    """
    records = event.get("Records", [])
    logger.info("Processing %d message(s) from FIFO queue", len(records))

    batch_item_failures = []

    # Initialize abstractions
    datastore = get_datastore()
    embedder = get_embedding_generator()

    try:
        for record in records:
            message_id = record["messageId"]
            try:
                process_message(record, datastore, embedder)
            except Exception as e:
                logger.error("Failed to process message %s: %s", message_id, e)
                batch_item_failures.append({"itemIdentifier": message_id})
    finally:
        datastore.close()
        flush_langfuse()

    if batch_item_failures:
        logger.warning(
            "Batch completed with %d failure(s) out of %d",
            len(batch_item_failures),
            len(records),
        )
    else:
        logger.info("Successfully processed all %d message(s)", len(records))

    return {"batchItemFailures": batch_item_failures}
