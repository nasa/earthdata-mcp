"""Temporal range extraction tool for parsing natural language time queries.

This module provides functionality to extract structured date ranges from
natural language queries using LLM-based parsing.
"""

from datetime import datetime, timezone
from typing import Dict
from pathlib import Path
import logging
import instructor
from langfuse import observe, get_client
from .input_model import TemporalRangeInput
from .output_model import TemporalRangeOutput

logger = logging.getLogger(__name__)

try:
    LANGFUSE = get_client()
except Exception as e:
    logger.warning("Failed to initialize Langfuse client: %s", e)
    LANGFUSE = None


@observe(name="get_temporal_ranges")
def get_temporal_ranges(
    query: TemporalRangeInput,
    provider: str = "bedrock",
    model_id: str = "amazon.nova-pro-v1:0",
) -> Dict:
    """Extract temporal date ranges from a natural language query.

     Args:
        query: A natural language string describing the desired time period.

    Returns:
        A dict with StartDate and EndDate datetime objects
        (dictionary representation of TemporalRangeOutput).
    """
    try:
        client = instructor.from_provider(f"{provider}/{model_id}")
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
            f"Failed to initialize instructor client with provider '{provider}' "
            f"and model '{model_id}': {e}"
        ) from e

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    # Load prompt from prompt.md file
    prompt_path = Path(__file__).parent / "prompt.md"

    if not prompt_path.exists():
        raise FileNotFoundError(f"Required prompt file not found: {prompt_path}")

    with open(prompt_path, "r", encoding="utf-8") as f:
        system_prompt = f.read().replace("{current_date}", today)

    try:
        output = client.create(
            modelId=model_id,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query.timerange_string},
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
            f"Failed to extract temporal ranges from query '{query.timerange_string}': {e}"
        ) from e

    return output.model_dump()
