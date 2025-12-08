from datetime import datetime, timezone
from typing import Any
from pathlib import Path
from pydantic import BaseModel
import instructor

# Try to use Bedrock, fall back to Ollama if credentials are not available
try:
    client = instructor.from_provider("bedrock/amazon.nova-pro-v1:0")
    model_id = "amazon.nova-pro-v1:0"
    use_bedrock = True
except Exception as e:
    print(f"Bedrock not available ({e}), falling back to Ollama")
    client = instructor.from_provider(
        "ollama/llama2",
        mode=instructor.Mode.JSON,
    )
    model_id = "llama2"
    use_bedrock = False


class DateRange(BaseModel):
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

    if use_bedrock:
        daterange = client.create(
            modelId=model_id,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query},
            ],
            response_model=DateRange,
        )
    else:
        # Ollama uses a different API
        daterange = client.chat.completions.create(
            model=model_id,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query},
            ],
            response_model=DateRange,
        )
    return [{"StartDate": daterange.start_date, "EndDate": daterange.end_date}]
