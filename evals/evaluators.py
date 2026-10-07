"""Langfuse evaluator functions for MCP regression tests."""

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from deepeval.metrics import MCPUseMetric
from deepeval.models import AmazonBedrockModel
from deepeval.test_case import LLMTestCase, MCPServer, MCPToolCall
from langfuse import Evaluation, observe
from pydantic import BaseModel, Field

from evals.sandbox_agent import _AgentResult, _bedrock_agent_task

# ---------------------------------------------------------------------------
# Inlined from mcpevals (mcp-agent is incompatible with mcp>=2; server.py
# requires mcp>=2 for build_resource_metadata_url added in that release)
# ---------------------------------------------------------------------------


@dataclass
class ToolCall:
    name: str
    arguments: dict[str, Any]
    result: Any
    start_time: float
    end_time: float
    is_error: bool = False


@dataclass
class TestMetrics:
    tool_calls: list[ToolCall] = field(default_factory=list)


@dataclass
class EvaluatorContext:
    inputs: Any
    output: Any
    expected_output: Any
    metadata: dict[str, Any] | None
    metrics: TestMetrics

    @property
    def tool_calls(self) -> list[ToolCall]:
        return self.metrics.tool_calls


class EvaluatorResult(BaseModel):
    passed: bool
    expected: Any = Field(default=None)
    actual: Any = Field(default=None)
    details: dict[str, Any] | None = Field(default=None)


class _SyncEvaluator(ABC):
    @abstractmethod
    def evaluate_sync(self, ctx: EvaluatorContext) -> EvaluatorResult: ...


@dataclass
class ToolWasCalled(_SyncEvaluator):
    tool_name: str
    min_times: int = 1

    def evaluate_sync(self, ctx: EvaluatorContext) -> EvaluatorResult:
        calls = [c for c in ctx.tool_calls if c.name == self.tool_name]
        return EvaluatorResult(passed=len(calls) >= self.min_times, actual=len(calls))


class ToolCalledWith(ToolWasCalled):
    def __init__(self, tool_name: str, expected_args: dict):
        super().__init__(tool_name)
        self.expected_args = expected_args

    def evaluate_sync(self, ctx: EvaluatorContext) -> EvaluatorResult:
        calls = [c for c in ctx.tool_calls if c.name == self.tool_name]
        matching = [
            c
            for c in calls
            if all(c.arguments.get(k) == v for k, v in self.expected_args.items())
        ]
        actual = (
            ", ".join(f"{self.tool_name}({c.arguments})" for c in calls)
            if calls
            else f"tool '{self.tool_name}' not called"
        )
        return EvaluatorResult(
            passed=bool(matching),
            expected=f"tool '{self.tool_name}' called with {self.expected_args}",
            actual=actual,
        )


@dataclass
class ToolSequence(_SyncEvaluator):
    expected_sequence: list[str]
    allow_other_calls: bool = True

    def evaluate_sync(self, ctx: EvaluatorContext) -> EvaluatorResult:
        actual = [c.name for c in ctx.tool_calls]
        if self.allow_other_calls:
            it = iter(actual)
            passed = all(item in it for item in self.expected_sequence)
        else:
            passed = actual == self.expected_sequence
        return EvaluatorResult(
            passed=passed, expected=self.expected_sequence, actual=actual
        )


DEFAULT_MODEL_ID = "amazon.nova-pro-v1:0"


def _get_agent_result(**kwargs) -> _AgentResult:
    """Return the cache-backed _AgentResult for this item's question."""
    input_val = kwargs.get("input", {})
    question = (
        input_val.get("question", "") if isinstance(input_val, dict) else str(input_val)
    )
    url = os.getenv("MCP_SERVER_URL", "http://127.0.0.1:5001/mcp/v1")
    model_id = os.getenv("BEDROCK_MODEL_ID", DEFAULT_MODEL_ID)
    return _bedrock_agent_task(question, url, model_id)


def _to_tool_calls(agent_result: _AgentResult) -> list[ToolCall]:
    return [
        ToolCall(
            name=inv.name,
            arguments=inv.args,
            result=inv.output,
            start_time=inv.start_time,
            end_time=inv.end_time,
            is_error=inv.is_error,
        )
        for inv in agent_result.invocations
    ]


def _make_eval_context(**kwargs) -> tuple[EvaluatorContext, list[ToolCall]]:
    """Build a shared EvaluatorContext from Langfuse evaluator kwargs."""
    agent_result = _get_agent_result(**kwargs)
    raw_calls = _to_tool_calls(agent_result)
    metrics = TestMetrics(tool_calls=raw_calls)
    ctx = EvaluatorContext(
        inputs=kwargs["input"],
        output=kwargs["output"],
        expected_output=kwargs["expected_output"],
        metadata=kwargs["metadata"],
        metrics=metrics,
    )
    return ctx, raw_calls


# --- EVALUATOR 1: DeepEval LLM Test Case Judge ---
@observe(as_type="evaluator")
def deepeval_mcp_use_judge(**kwargs):
    """Evaluates multi-turn tool usage using AWS Bedrock as an LLM judge."""
    agent_result = _get_agent_result(**kwargs)
    mcp_tools_called = [
        MCPToolCall(name=inv.name, args=inv.args, result=inv.mcp_result)
        for inv in agent_result.invocations
    ]

    convo_test_case = LLMTestCase(
        input=kwargs["input"].get("question", ""),
        actual_output=kwargs["output"],
        mcp_servers=[
            MCPServer(
                server_name="earthdata-mcp",
                transport="streamable-http",
                available_tools=agent_result.available_tools,
            )
        ],
        mcp_tool_calls=mcp_tools_called,
    )

    bedrock_model = AmazonBedrockModel(
        model=os.getenv("DEEPEVAL_MODEL", DEFAULT_MODEL_ID),
        region=os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1")),
        generation_kwargs={"temperature": 0},
    )

    metric = MCPUseMetric(
        threshold=0.5,
        model=bedrock_model,
        include_reason=True,
        async_mode=True,
        async_mode=True,
    )
    metric.measure(convo_test_case)
    metric.measure(convo_test_case)
    # Run in a fresh thread to avoid "event loop already running" when Langfuse's
    # experiment runner calls evaluators from a thread that already has a loop.
    # with ThreadPoolExecutor(max_workers=1) as pool:
    #     pool.submit(metric.measure, convo_test_case).result()
    # with ThreadPoolExecutor(max_workers=1) as pool:
    #     pool.submit(metric.measure, convo_test_case).result()

    return Evaluation(
        name="deepeval_mcp_alignment", value=metric.score, comment=metric.reason
    )


# --- EVALUATOR 2: Tool Was Called ---
def mcp_eval_tool_assertion(**kwargs):
    """Hard check: the target tool must appear at least once in the trace."""
    target_tool = kwargs["metadata"].get("expected_tool_call")
    if not target_tool:
        return None
    ctx, _ = _make_eval_context(**kwargs)

    result = ToolWasCalled(tool_name=target_tool, min_times=1).evaluate_sync(ctx)
    return Evaluation(
        name="mcp_eval_tool_coverage",
        value=1.0 if result.passed else 0.0,
        comment=f"Target: {target_tool}. Calls found: {result.actual}.",
    )


# --- EVALUATOR 3: Argument Quality ---
def mcp_eval_argument_assertion(**kwargs):
    """Check that the target tool was called with the expected arguments."""
    metadata = kwargs["metadata"]
    expected_args = metadata.get("expected_tool_arguments")
    if not expected_args:
        return None

    ctx, _ = _make_eval_context(**kwargs)
    target_tool = metadata.get("expected_tool_call", "unknown_tool")

    result = ToolCalledWith(
        tool_name=target_tool, expected_args=expected_args
    ).evaluate_sync(ctx)

    return Evaluation(
        name="mcp_eval_argument_quality",
        value=1.0 if result.passed else 0.0,
        comment=str(result.actual),
    )


# --- EVALUATOR 4: Tool Call Sequence ---
def mcp_eval_sequence_assertion(**kwargs):
    """Check that tools were called in the expected order across a multi-turn trace."""
    metadata = kwargs["metadata"]
    expected_sequence = metadata.get("expected_tool_sequence")
    if not expected_sequence:
        return None

    ctx, _ = _make_eval_context(**kwargs)

    result = ToolSequence(
        expected_sequence=expected_sequence, allow_other_calls=True
    ).evaluate_sync(ctx)

    return Evaluation(
        name="mcp_eval_tool_sequence",
        value=1.0 if result.passed else 0.0,
        comment=f"Expected: {result.expected}. Actual: {result.actual}.",
    )


# --- EVALUATOR 5: Tool Call Volume ---
def mcp_eval_tool_call_counts(**kwargs):
    """Record per-tool call counts as an observability signal — never pass/fail."""
    agent_result = _get_agent_result(**kwargs)
    counts: dict[str, int] = {}
    for inv in agent_result.invocations:
        counts[inv.name] = counts.get(inv.name, 0) + 1

    total = sum(counts.values())
    max_ct = max(counts.values()) if counts else 0
    breakdown = ", ".join(f"{name}×{n}" for name, n in sorted(counts.items()))
    return Evaluation(
        name="mcp_eval_tool_call_max_counts",
        value=max_ct,
        comment=f"total={total} | {breakdown}" if breakdown else "no tool calls",
    )


# --- EVALUATOR 6: Abstention ---
def mcp_eval_abstention(**kwargs):
    """Pass only when no tools were called — for off-topic / out-of-bounds items."""
    if not kwargs["metadata"].get("expected_no_tool_calls"):
        return None

    agent_result = _get_agent_result(**kwargs)
    passed = len(agent_result.invocations) == 0
    tools_used = [inv.name for inv in agent_result.invocations]
    return Evaluation(
        name="mcp_eval_abstention",
        value=1.0 if passed else 0.0,
        comment=(
            "Correctly abstained from tool use."
            if passed
            else f"Unexpectedly called: {tools_used}"
        ),
    )


# --- EVALUATOR 7: No Hallucinated Arguments ---
def mcp_eval_no_hallucinated_args(**kwargs):
    """Fail if the model passed argument keys not present in the tool's inputSchema."""
    metadata = kwargs["metadata"]
    if not metadata.get("check_no_hallucinated_args"):
        return None
    target_tool = metadata.get("expected_tool_call")
    if not target_tool:
        return None

    agent_result = _get_agent_result(**kwargs)

    schema_props: set[str] = set()
    for tool in agent_result.available_tools:
        if tool.get("name") == target_tool:
            schema_props = set(tool.get("inputSchema", {}).get("properties", {}).keys())
            break

    if not schema_props:
        return None

    hallucinated: list[str] = []
    for inv in agent_result.invocations:
        if inv.name == target_tool:
            hallucinated.extend(k for k in inv.args if k not in schema_props)

    passed = len(hallucinated) == 0
    return Evaluation(
        name="mcp_eval_no_hallucinated_args",
        value=1.0 if passed else 0.0,
        comment=(
            "No hallucinated arguments."
            if passed
            else f"Hallucinated args: {hallucinated}"
        ),
    )


ALL_EVALUATORS = [
    deepeval_mcp_use_judge,
    mcp_eval_tool_assertion,
    mcp_eval_argument_assertion,
    mcp_eval_sequence_assertion,
    mcp_eval_tool_call_counts,
    mcp_eval_abstention,
    mcp_eval_no_hallucinated_args,
]
