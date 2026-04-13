"""Collection formatting utilities for RAG evaluation."""


def format_collection_context(
    collection: dict,
    fields: list[str],
) -> str:
    """
    Format a single collection into a context string.

    Args:
        collection: Collection dictionary
        fields: Fields to extract from the collection

    Returns:
        Formatted context string with "Field Name: value" format
    """
    parts = []
    for field in fields:
        value = collection.get(field)
        if value:
            field_label = field.replace("_", " ").title()
            parts.append(f"{field_label}: {value}")
    return "\n".join(parts)


def generate_contexts_from_collections(
    collections: list[dict],
    fields: list[str],
) -> list[str]:
    """
    Generate context strings from a list of collections.

    Args:
        collections: List of collection dictionaries
        fields: Fields to extract from each collection

    Returns:
        List of formatted context strings
    """
    return [format_collection_context(c, fields) for c in collections]


def generate_answer_from_collections(
    collections: list[dict],
    fields: list[str],
) -> str:
    """
    Generate a simple answer from collections.

    WARNING: For evaluation purposes, you should use the actual system-generated
    answer, not this auto-generated one. Using this creates circularity where
    contexts and answer are derived from the same source, artificially inflating
    metrics like Faithfulness.

    This function is only useful for:
    - Testing/debugging
    - Cases where you only have collections but no generated answer

    Args:
        collections: List of collection dictionaries
        fields: Fields used (first field assumed to be the primary identifier)

    Returns:
        Simple answer string
    """
    if not collections:
        return "No relevant data collections were found for your query."

    # Use first field as primary identifier (usually title)
    primary_field = fields[0] if fields else next(iter(collections[0].keys()), "id")
    top_identifiers = ", ".join(str(c.get(primary_field, "Unknown")) for c in collections[:3])
    return (
        f"Found {len(collections)} relevant data collections. "
        f"Top matches include: {top_identifiers}."
    )
