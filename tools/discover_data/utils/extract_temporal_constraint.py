"""
LLM-based temporal constraint extraction.

Uses an LLM to parse natural language and extract start/end dates.
"""

# pylint: disable=duplicate-code  # Intentional code patterns shared with extract_spatial_constraint.py

import logging
from datetime import UTC, datetime

import instructor
from langfuse import observe

from tools.models.constraints import TemporalConstraint
from tools.discover_data.models.llm import TemporalRangeOutput
from tools.discover_data.utils.llm_extraction import MODEL_ID, PROVIDER, load_extraction_prompt
from util.langfuse import trace_update

logger = logging.getLogger(__name__)


@observe(name="extract_temporal_constraint")
def extract_temporal_constraint(query: str) -> TemporalConstraint:
    """Extract temporal constraints from a natural language query.

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

    try:
        client = instructor.from_provider(f"{PROVIDER}/{MODEL_ID}")
    except Exception as e:
        trace_update(
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
        output = client.create(
            modelId=MODEL_ID,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query},
            ],
            response_model=TemporalRangeOutput,
        )
    except Exception as e:
        trace_update(
            tags=["error", "llm_error"],
            metadata={"error_type": "llm_error", "message": str(e), "success": False},
        )
        raise RuntimeError(f"Failed to extract temporal ranges from query '{query}': {e}") from e

    trace_update(
        tags=["success", "temporal_extraction"],
        metadata={"success": True},
    )

    return TemporalConstraint(
        start_date=output.start_date,
        end_date=output.end_date,
        reasoning=output.reasoning,
    )
