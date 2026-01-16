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
from .input_model import TimeRangeInput
from .output_model import TimeRangeOutput

logger = logging.getLogger(__name__)

# Try to use Bedrock, fall back to Ollama if credentials are not available
try:
    LANGFUSE = get_client()
except Exception as e:
    logger.warning("Failed to initialize Langfuse client: %s", e)
    LANGFUSE = None


@observe(name="extract_time_range")
def extract_time_range(
    query: TimeRangeInput,
    provider: str = "bedrock",
    model_id: str = "amazon.nova-pro-v1:0",
) -> Dict:
    """Extract datetime ranges from a natural language query.

    Resolves natural language queries into ISO 8601 start/end datetimes.
    Handles explicit ranges, relative dates ('since 2020', 'past 5 years'),
    and seasonal/event terms ('Summer 2023', 'Hurricane Season').

    Args:
        query: Input containing the full user query with temporal references.

    Returns:
        A dict with StartDate and EndDate datetime objects
        (dictionary representation of TimeRangeOutput).
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
                {"role": "user", "content": query.query},
            ],
            response_model=TimeRangeOutput,
        )
    except Exception as e:
        if LANGFUSE:
            LANGFUSE.update_current_trace(
                tags=["error", "llm_error"],
                metadata={"error_type": "llm_error", "message": e, "success": False},
            )
        raise RuntimeError(
            f"Failed to extract temporal ranges from query '{query.query}': {e}"
        ) from e

    return output.model_dump()
