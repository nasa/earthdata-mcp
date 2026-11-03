"""Pytest entry point for the Langfuse MCP regression experiment."""

import os

import pytest

from evals.regression_test import run_experiment


@pytest.mark.skipif(
    os.getenv("RUN_MCP_REGRESSION") != "1",
    reason="Set RUN_MCP_REGRESSION=1 to run the live Langfuse/MCP regression suite",
)
def test_mcp_regression_experiment_passes():
    """Run the hosted golden set and fail CI when any gating evaluator fails."""
    result, passed = run_experiment()
    assert passed, f"Regression failures: {result}"
