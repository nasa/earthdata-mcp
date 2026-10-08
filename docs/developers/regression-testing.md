# Regression Testing

The regression suite validates that changes to the Earthdata MCP server don't break established tool-selection and argument behaviors. It runs a curated golden dataset through a live Bedrock agentic loop and scores the results in Langfuse.

This is an **end-to-end behavioral test**, not a unit test. It requires a running MCP server, AWS credentials, and Langfuse credentials.

---

## Why

CMR API responses, tool schemas, and prompt instructions change over time. Without behavioral regression tests, a refactor or schema update can silently cause the model to call the wrong tool, pass the wrong arguments, or stop calling tools altogether. The regression suite catches these regressions before deploy by comparing live model behavior against a versioned golden dataset.

---

## Running

Prerequisites: MCP server running locally (`uv run server.py http`), `.env` file with Langfuse and AWS credentials set.

```bash
# Push the golden dataset to Langfuse (run once, or after editing the dataset file)
uv run python evals/regression_test.py publish

# Run experiments and print scores
uv run python evals/regression_test.py run

# Publish then run in one shot
uv run python evals/regression_test.py publish-and-run
```

**CI gate** — set `RUN_MCP_REGRESSION=1` to include the test in `pytest`:

```bash
RUN_MCP_REGRESSION=1 uv run pytest tests/regression/test_regression.py -v
```

Without that env var the test is skipped, so normal `pytest` runs are unaffected.

---

## Architecture

```
evals/mcp_regression_dataset.json   ← golden dataset (version-controlled)
        │
        ▼ publish
   Langfuse Dataset
        │
        ▼ run_experiment
   sandbox_agent.py                 ← Bedrock + MCP agentic loop (cache backed)
        │
        ▼ evaluators run against cached results
   Langfuse Experiment Run
        │
        ▼ viewable in Langfuse UI
   Datasets tab / Scores tab / Dashboard
```

### Golden Dataset (`evals/mcp_regression_dataset.json`)

Each item defines a question, expected outputs, and metadata that drives the evaluators:

| Field | Purpose |
|---|---|
| `id` | Stable identifier — used by Langfuse to upsert items without duplication |
| `input.question` | The natural-language question sent to the model |
| `metadata.expected_tool_call` | The tool that must be called |
| `metadata.expected_tool_arguments` | Argument key/value pairs the tool must receive |
| `metadata.expected_tool_sequence` | Ordered list of tools for multi-turn queries |
| `metadata.expected_no_tool_calls` | Set to `true` for off-topic / abstention cases |
| `metadata.check_no_hallucinated_args` | Enable hallucination check against the tool's `inputSchema` |

Edit this file to add or update cases, then run `publish` to push changes to Langfuse.

### Agent Loop (`evals/sandbox_agent.py`)

`_bedrock_agent_task(question, url, model_id)` runs a synchronous Bedrock converse loop against the live MCP server. It is decorated with `@cache` (`functools.lru_cache`), so the first call for a given `(question, url, model_id)` tuple hits Bedrock; all subsequent calls (from evaluators) return the cached `_AgentResult` without a second invocation.

This is the task→evaluator handoff: the experiment task primes the cache, all seven evaluators read from it.

### Evaluators (`evals/evaluators.py`)

Evaluators are plain functions passed to `dataset.run_experiment`. Each receives Langfuse item kwargs and returns a `langfuse.Evaluation` (or `None` to skip). They call `_get_agent_result(**kwargs)` which reconstructs the cache key and hits the cached result.

| Evaluator | Langfuse metric name | What it measures |
|---|---|---|
| `deepeval_mcp_use_judge` | `deepeval_mcp_alignment` | LLM-as-judge: did the model use MCP tools appropriately end-to-end? Uses [DeepEval `MCPUseMetric`](https://docs.confident-ai.com/docs/metrics-mcp-tool-correctness) with Bedrock as the judge model. Score 0–1. |
| `mcp_eval_tool_assertion` | `mcp_eval_tool_coverage` | Hard binary check: was `expected_tool_call` called at least once? |
| `mcp_eval_argument_assertion` | `mcp_eval_argument_quality` | Were the expected argument key/value pairs present in the call to `expected_tool_call`? |
| `mcp_eval_sequence_assertion` | `mcp_eval_tool_sequence` | Did the tools appear in the expected order (non-contiguous matches allowed)? |
| `mcp_eval_tool_call_counts` | `mcp_eval_tool_call_max_counts` | Observability only — records max per-tool call counts. |
| `mcp_eval_abstention` | `mcp_eval_abstention` | For off-topic items: did the model correctly make zero tool calls? |
| `mcp_eval_no_hallucinated_args` | `mcp_eval_no_hallucinated_args` | Did the model pass any argument keys not declared in the tool's `inputSchema`? |

The `mcp_eval_*` evaluators (2–7) are implemented directly in `evals/evaluators.py` using inlined dataclass logic (previously the `mcpevals` library — removed because `mcp-agent`, its transitive dependency, is incompatible with `mcp>=2` which the server requires). The `deepeval_mcp_use_judge` evaluator uses [DeepEval](https://docs.confident-ai.com/).

Useful references:
* [DeepEval MCPUseMetric](https://deepeval.com/docs/metrics-mcp-use)

---

## Viewing Results in Langfuse

After a run, results are available in three places in the Langfuse UI:

- **Datasets tab** — per-item scores across experiment runs; useful for comparing runs side-by-side
- **Scores tab** — aggregate score distributions per metric
- **Dashboard** — trend charts over time; useful for tracking regressions across deploys

---

## Adding Test Cases

1. Add an entry to `evals/mcp_regression_dataset.json` with a unique `id`.
2. Set `metadata` fields for whichever evaluators should run (omit fields you don't need — evaluators skip when their required metadata key is absent).
3. Run `uv run python evals/regression_test.py publish` to push to Langfuse.
4. Run `uv run python evals/regression_test.py run` to verify scores.
