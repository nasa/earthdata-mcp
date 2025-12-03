"""
Temporal Ranges Tool

Update this once the tool is implemented
"""

from datetime import datetime
from typing import Any
from pathlib import Path
from pydantic import BaseModel
import instructor

client = instructor.from_provider("bedrock/amazon.nova-pro-v1:0")


class DateRange(BaseModel):
    """
    Update this once the tool is implemented
    """

    start_date: datetime | None = None
    end_date: datetime | None = None
    reasoning: str | None = None


def get_temporal_ranges(query: str) -> Any:
    """Get a list of collections form CMR based on keywords.

    Args:
        keywords: A string of text to search collections with.
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    # Load prompt from prompt.md file
    prompt_path = Path(__file__).parent / "prompt.md"
    with open(prompt_path, "r", encoding="utf-8") as f:
        system_prompt = f.read().replace("{current_date}", today)

    daterange = client.create(
        modelId="amazon.nova-pro-v1:0",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query},
        ],
        response_model=DateRange,
    )
    return [{"StartDate": daterange.start_date, "EndDate": daterange.end_date}]
