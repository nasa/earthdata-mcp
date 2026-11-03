"""Langfuse-backed MCP regression tests for the Earthdata server."""

import argparse
import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langfuse import get_client

from evals.evaluators import ALL_EVALUATORS, DEFAULT_MODEL_ID
from evals.sandbox_agent import _bedrock_agent_task

load_dotenv()

DEFAULT_DATASET_NAME = "mcp-regression-golden-set"
DEFAULT_DATASET_FILE = Path(__file__).with_name("mcp_regression_dataset.json")
DEFAULT_EXPERIMENT_NAME = "MCP Pre-Deploy Core Regression Suite"

# Evaluators that report observability signals rather than pass/fail gates.
# Their scores should never cause the regression suite to fail.
NON_GATING_EVALUATORS = frozenset(
    {
        # LLM-judge score, often wrong with AWS Nova, informational only
        "deepeval_mcp_alignment",
        # Call count for tool with most calls, not a pass/fail signal
        "mcp_eval_tool_call_max_counts",
    }
)

# Text formatting
BOLD = "\033[1m"
RED = "\033[31m"
RESET = "\033[0m"


def my_mcp_agent_task(*, item, **kwargs):
    """Run a Bedrock agentic loop against the MCP server; let the model choose tools."""
    del kwargs
    if item.metadata is None:
        item.metadata = {}

    question = (
        item.input.get("question", "")
        if isinstance(item.input, dict)
        else str(item.input)
    )
    url = os.getenv("MCP_SERVER_URL", "http://127.0.0.1:5001/mcp/v1")
    model_id = os.getenv("BEDROCK_MODEL_ID", DEFAULT_MODEL_ID)

    agent_result = _bedrock_agent_task(question, url, model_id)

    item.metadata["model_used"] = model_id
    item.metadata["input_tokens"] = agent_result.input_tokens
    item.metadata["output_tokens"] = agent_result.output_tokens
    item.metadata.setdefault(
        "expected_tool_call",
        agent_result.invocations[0].name if agent_result.invocations else None,
    )

    return json.dumps(agent_result.final_output, default=str)


def _load_dataset_definition(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as dataset_file:
        definition = json.load(dataset_file)

    if not isinstance(definition.get("items"), list) or not definition["items"]:
        raise ValueError(
            f"Dataset definition {path} must contain a non-empty 'items' list"
        )
    return definition


def publish_dataset(
    *,
    dataset_name: str = DEFAULT_DATASET_NAME,
    dataset_file: Path = DEFAULT_DATASET_FILE,
) -> Any:
    """Create or update the versioned regression cases in Langfuse."""
    langfuse = get_client()
    definition = _load_dataset_definition(dataset_file)
    description = definition.get(
        "description", "Golden MCP tool-selection and argument regression cases."
    )

    try:
        dataset = langfuse.get_dataset(dataset_name)
    except Exception:  # noqa: BLE001 - the SDK has no get-or-create operation
        dataset = langfuse.create_dataset(name=dataset_name, description=description)

    for item in definition["items"]:
        if not isinstance(item, dict) or not item.get("id"):
            raise ValueError("Every dataset item must define a stable 'id'")
        langfuse.create_dataset_item(
            dataset_name=dataset_name,
            id=item["id"],
            input=item.get("input", {}),
            expected_output=item.get("expected_output"),
            metadata=item.get("metadata", {}),
        )

    langfuse.flush()
    print(
        f"Published {len(definition['items'])} items to Langfuse dataset '{dataset_name}'."
    )
    return dataset


def _summarize_experiment(result: Any) -> tuple[bool, list[dict[str, Any]]]:
    """Walk per-item evaluation scores and decide overall pass/fail.

    Returns (all_passed, failures), where `failures` lists, per failing
    item, which gating evaluators scored below 1.0 and what they returned.
    """
    failures: list[dict[str, Any]] = []

    for item_result in result.item_results:
        gating_evals = [
            e for e in item_result.evaluations if e.name not in NON_GATING_EVALUATORS
        ]
        failed = [e for e in gating_evals if e.value < 1.0]

        if failed:
            failures.append(
                {
                    "item_id": item_result.item.id,
                    "failed_evaluators": [
                        {"name": e.name, "value": e.value, "comment": e.comment} for e in failed
                    ],
                }
            )

    return (len(failures) == 0, failures)


def run_experiment(
    *,
    dataset_name: str = DEFAULT_DATASET_NAME,
    experiment_name: str = DEFAULT_EXPERIMENT_NAME,
    model_id: str = "",
) -> Any:
    """Pull a Langfuse dataset, run it with a Bedrock agentic loop, and return results."""
    langfuse = get_client()
    resolved_model = model_id or os.getenv("BEDROCK_MODEL_ID", DEFAULT_MODEL_ID)
    tagged_experiment_name = f"{experiment_name} [{resolved_model}]"

    dataset = langfuse.get_dataset(dataset_name)
    result = dataset.run_experiment(
        name=tagged_experiment_name,
        task=my_mcp_agent_task,
        evaluators=ALL_EVALUATORS,
        max_concurrency=int(os.getenv("REGRESSION_MAX_CONCURRENCY", "3")),
    )
    # Print all results
    print(result.format(include_item_results=True).replace("\\n", "\n"))

    # Print failed gating evaluators by dataset item
    passed, failures = _summarize_experiment(result)
    if failures:
        print(f"\n{RED}{BOLD}‼️ Regression failures detected:{RESET}")
        for failure in failures:
            print(
                f"  {BOLD}{failure['item_id']}{RESET}: "
                f"{json.dumps(failure['failed_evaluators'], indent = 4)}"
            )

    return result, passed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Earthdata MCP Langfuse regression suite"
    )
    parser.add_argument(
        "command",
        choices=("publish", "run", "publish-and-run"),
        help="Publish golden cases, run the Langfuse dataset, or do both",
    )
    parser.add_argument("--dataset-name", default=DEFAULT_DATASET_NAME)
    parser.add_argument("--dataset-file", type=Path, default=DEFAULT_DATASET_FILE)
    parser.add_argument("--experiment-name", default=DEFAULT_EXPERIMENT_NAME)
    parser.add_argument(
        "--model-id",
        default="",
        help="Bedrock model ID (default: BEDROCK_MODEL_ID env var or amazon.nova-pro-v1:0)",
    )
    args = parser.parse_args()

    if args.command in ("publish", "publish-and-run"):
        publish_dataset(dataset_name=args.dataset_name, dataset_file=args.dataset_file)
    if args.command in ("run", "publish-and-run"):
        _, passed = run_experiment(
            dataset_name=args.dataset_name,
            experiment_name=args.experiment_name,
            model_id=args.model_id,
        )
        return 0 if passed else 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
