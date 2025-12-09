from datetime import datetime, timezone
from typing import Any
from pathlib import Path
from pydantic import BaseModel
import instructor


class DateRange(BaseModel):
    start_date: datetime | None = None
    end_date: datetime | None = None
    reasoning: str | None = None


def get_temporal_ranges(
    query: str,
    provider="bedrock",
    model_id="amazon.nova-pro-v1:0",
) -> Any:
    """Extract temporal date ranges from a natural language query.

     Args:
        query: A natural language string describing the desired time period.

    Returns:
        A list containing a dict with StartDate and EndDate datetime objects.
    """
    client = instructor.from_provider(f"{provider}/{model_id}")

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    # Load prompt from prompt.md file
    prompt_path = Path(__file__).parent / "prompt.md"
    with open(prompt_path, "r", encoding="utf-8") as f:
        system_prompt = f.read().replace("{current_date}", today)

    try:
        daterange = client.create(
            modelId=model_id,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query},
            ],
            response_model=DateRange,
        )
    except Exception as e:
        raise RuntimeError(
            f"Failed to extract temporal ranges from query '{query}': {e}"
        ) from e

    return [{"StartDate": daterange.start_date, "EndDate": daterange.end_date}]
