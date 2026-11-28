"""Pytest entry point for the Langfuse MCP regression experiment."""

import os

import pytest

from evals.regression_test import run_all_experiments


@pytest.mark.skipif(
    os.getenv("RUN_MCP_REGRESSION") != "1",
    reason="Set RUN_MCP_REGRESSION=1 to run the live Langfuse/MCP regression suite",
)
def test_mcp_regression_experiment_passes():
    """Run the hosted live and mocked golden sets and fail CI when any gating evaluator fails."""
    results, passed = run_all_experiments()
    assert passed, f"Regression failures: {results}"
