"""
LLM-based temporal constraint extraction.

Uses an LLM to parse natural language and extract start/end dates.

Two-layer design:
  - _extract_temporal_with_llm: Pure LLM parsing (testable in isolation)
  - extract_temporal_constraint_from_query: Public wrapper with guards + error handling
"""

# pylint: disable=duplicate-code  # Intentional code patterns shared with extract_spatial_constraint.py

import logging
from datetime import UTC, datetime

import instructor
from langfuse import observe

from tools.discover_data.input_model import TemporalConstraint
from tools.discover_data.utils.llm_extraction import MODEL_ID, PROVIDER, load_extraction_prompt
from util.langfuse import initialize_langfuse_client

logger = logging.getLogger(__name__)

LANGFUSE = initialize_langfuse_client()


@observe(name="extract_temporal_from_query")
def _extract_temporal_with_llm(query: str) -> TemporalConstraint:
    """LLM-only temporal extraction used by the public wrapper.

    Args:
        query: Natural language description of a time period.

    Returns:
        TemporalConstraint with start/end and reasoning; raises on LLM failures.
    """
    try:
        client = instructor.from_provider(f"{PROVIDER}/{MODEL_ID}")
    except Exception as e:
        if LANGFUSE:
            LANGFUSE.update_current_trace(
                tags=["error", "client_init_error"],
                metadata={
                    "error_type": "client_init_error",
                    "message": str(e),
                    "success": False,
                },
            )
        raise RuntimeError(
            f"Failed to initialize instructor client with provider '{PROVIDER}' "
            f"and model '{MODEL_ID}': {e}"
        ) from e

    today = datetime.now(UTC).strftime("%Y-%m-%d")
    system_prompt = load_extraction_prompt("temporal_extraction.md", today)

    try:
        from pydantic import BaseModel

        class TemporalRangeOutput(BaseModel):
            """Output model for temporal range extraction from LLM."""
            start_date: datetime | None = None
            end_date: datetime | None = None
            reasoning: str | None = None

        output = client.create(
            modelId=MODEL_ID,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query},
            ],
            response_model=TemporalRangeOutput,
        )
    except Exception as e:
        if LANGFUSE:
            LANGFUSE.update_current_trace(
                tags=["error", "llm_error"],
                metadata={"error_type": "llm_error", "message": e, "success": False},
            )
        raise RuntimeError(
            f"Failed to extract temporal ranges from query '{query}': {e}"
        ) from e

    if LANGFUSE:
        LANGFUSE.update_current_trace(
            tags=["success", "temporal_extraction"],
            metadata={"success": True},
        )

    return TemporalConstraint(
        start_date=output.start_date,
        end_date=output.end_date,
        reasoning=output.reasoning,
    )


@observe(name="extract_temporal_constraint")
def extract_temporal_constraint(
    query: str,
) -> TemporalConstraint:
    """Convert a natural language query to a temporal constraint.

    Args:
        query: Natural language description of a time period.

    Returns:
        TemporalConstraint with extracted start/end dates and reasoning.
    """
    if not query:
        logger.warning("Empty query provided for temporal constraint extraction.")
        return TemporalConstraint(
            start_date=None,
            end_date=None,
            reasoning="No temporal information found in query",
        )

    return _extract_temporal_with_llm(query)
