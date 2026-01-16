"""
Extraction functions for CMR concept metadata.

Extracts text chunks and KMS term references from UMM metadata
for collections, variables, and citations.
"""

import logging
from typing import Any

from util.cmr.client import CMRError
from util.models import ConceptMessage, EmbeddingChunk, ExtractionResult, KMSTerm

logger = logging.getLogger(__name__)

# Field mappings: UMM field names -> attribute names for each concept type
COLLECTION_FIELDS = {
    "EntryTitle": "title",
    "Abstract": "abstract",
    "Purpose": "purpose",
}

VARIABLE_FIELDS = {
    "Name": "name",
    "LongName": "long_name",
    "Definition": "definition",
}

CITATION_FIELDS = {
    "Name": "name",
    "Abstract": "abstract",
}


def extract_text_chunks(
    concept_type: str,
    concept_id: str,
    metadata: dict[str, Any],
    field_map: dict[str, str],
) -> list[EmbeddingChunk]:
    """
    Extract text fields from metadata based on field mapping.

    Args:
        concept_type: Type of concept (collection, variable, citation)
        concept_id: CMR concept ID
        metadata: Raw UMM metadata from CMR
        field_map: Maps UMM field names -> attribute names

    Returns:
        List of EmbeddingChunk for each non-empty field found
    """
    chunks = []
    for umm_field, attribute in field_map.items():
        if text := metadata.get(umm_field):
            chunks.append(
                EmbeddingChunk(
                    concept_type=concept_type,
                    concept_id=concept_id,
                    attribute=attribute,
                    text_content=text,
                )
            )
    return chunks


def extract_citation_authors(
    concept_id: str,
    metadata: dict[str, Any],
) -> EmbeddingChunk | None:
    """Extract formatted author names from citation metadata."""
    citation_metadata = metadata.get("CitationMetadata", {})
    authors = citation_metadata.get("Author", [])

    if not authors:
        return None

    names = []
    for author in authors:
        given = author.get("Given", "")
        family = author.get("Family", "")
        if given and family:
            names.append(f"{given} {family}")
        elif family:
            names.append(family)

    if not names:
        return None

    return EmbeddingChunk(
        concept_type="citation",
        concept_id=concept_id,
        attribute="authors",
        text_content="; ".join(names),
    )


def extract_citation_publisher(
    concept_id: str,
    metadata: dict[str, Any],
) -> EmbeddingChunk | None:
    """Extract publisher from citation metadata."""
    citation_metadata = metadata.get("CitationMetadata", {})
    if publisher := citation_metadata.get("Publisher"):
        return EmbeddingChunk(
            concept_type="citation",
            concept_id=concept_id,
            attribute="publisher",
            text_content=publisher,
        )
    return None


def extract_science_keywords(metadata: dict[str, Any]) -> list[KMSTerm]:
    """
    Extract science keyword terms from UMM metadata.

    Science keywords are hierarchical (Category > Topic > Term > VariableLevel1-3).
    We extract the most specific level available for each keyword.
    """
    terms = []
    for kw in metadata.get("ScienceKeywords", []):
        term = (
            kw.get("VariableLevel3")
            or kw.get("VariableLevel2")
            or kw.get("VariableLevel1")
            or kw.get("Term")
        )
        if term:
            terms.append(KMSTerm(term=term, scheme="sciencekeywords"))
    return terms


def extract_platforms_and_instruments(metadata: dict[str, Any]) -> list[KMSTerm]:
    """Extract platform and instrument terms from collection metadata."""
    terms = []
    for platform in metadata.get("Platforms", []):
        if name := platform.get("ShortName"):
            terms.append(KMSTerm(term=name, scheme="platforms"))

        for instrument in platform.get("Instruments", []):
            if name := instrument.get("ShortName"):
                terms.append(KMSTerm(term=name, scheme="instruments"))
    return terms


def extract_from_collection(concept_id: str, metadata: dict[str, Any]) -> ExtractionResult:
    """Extract embeddable data from a collection's UMM-C metadata."""
    chunks = extract_text_chunks("collection", concept_id, metadata, COLLECTION_FIELDS)
    kms_terms = extract_science_keywords(metadata) + extract_platforms_and_instruments(metadata)
    return ExtractionResult(chunks=chunks, kms_terms=kms_terms)


def extract_from_variable(concept_id: str, metadata: dict[str, Any]) -> ExtractionResult:
    """Extract embeddable data from a variable's UMM-Var metadata."""
    chunks = extract_text_chunks("variable", concept_id, metadata, VARIABLE_FIELDS)
    kms_terms = extract_science_keywords(metadata)
    return ExtractionResult(chunks=chunks, kms_terms=kms_terms)


def extract_from_citation(concept_id: str, metadata: dict[str, Any]) -> ExtractionResult:
    """Extract embeddable data from a citation."""
    chunks = extract_text_chunks("citation", concept_id, metadata, CITATION_FIELDS)

    if author_chunk := extract_citation_authors(concept_id, metadata):
        chunks.append(author_chunk)
    if publisher_chunk := extract_citation_publisher(concept_id, metadata):
        chunks.append(publisher_chunk)

    return ExtractionResult(chunks=chunks, kms_terms=[])


def extract_data(message: ConceptMessage, metadata: dict[str, Any]) -> ExtractionResult:
    """Route to the appropriate extractor based on concept type."""
    extractors = {
        "collection": extract_from_collection,
        "variable": extract_from_variable,
        "citation": extract_from_citation,
    }
    extractor = extractors.get(message.concept_type)
    if not extractor:
        logger.warning("Unknown concept type: %s", message.concept_type)
        return ExtractionResult()

    return extractor(message.concept_id, metadata)


def extract_concept_info(concept_type: str, item: dict[str, Any]) -> dict[str, Any]:
    """
    Extract concept ID and revision ID from a CMR search result item.

    Args:
        concept_type: Type of concept
        item: CMR item from search results

    Returns:
        Dictionary with concept-type, concept-id, revision-id, action

    Raises:
        CMRError: If concept-id or revision-id is missing.
    """
    meta = item.get("meta", {})
    concept_id = meta.get("concept-id")
    revision_id = meta.get("revision-id")

    if not concept_id or not revision_id:
        raise CMRError(f"Missing concept-id or revision-id in item: {meta}")

    return {
        "concept-type": concept_type,
        "concept-id": concept_id,
        "revision-id": revision_id,
        "action": "concept-update",
    }
