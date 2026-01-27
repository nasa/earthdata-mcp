"""Shared LLM extraction utilities for temporal and spatial constraints.

Consolidates common patterns used by both constraint extraction modules
to avoid code duplication.
"""

from pathlib import Path

PROVIDER = "bedrock"
MODEL_ID = "amazon.nova-pro-v1:0"


def load_extraction_prompt(prompt_filename: str, current_date: str) -> str:
    """
    Load and prepare an extraction prompt from the prompts directory.

    Args:
        prompt_filename: Filename in tools/discover_data/utils/prompts/ (e.g., "spatial_extraction.md")
        current_date: Current date string to replace in prompt (format: "YYYY-MM-DD")

    Returns:
        Prepared prompt text with {current_date} placeholder replaced

    Raises:
        FileNotFoundError: If prompt file doesn't exist
    """
    prompt_path = Path(__file__).parent / "prompts" / prompt_filename

    if not prompt_path.exists():
        raise FileNotFoundError(f"Required prompt file not found: {prompt_path}")

    with open(prompt_path, encoding="utf-8") as f:
        return f.read().replace("{current_date}", current_date)
