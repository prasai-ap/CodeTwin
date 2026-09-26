"""IBM Bob tools for repository-aware CodeTwin impact validation."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from codetwin.api_client import request_api

mcp = FastMCP(
    "CodeTwin",
    instructions=(
        "Use these tools to independently inspect CodeTwin repository snapshots. "
        "Predicted impact is deterministic analyzer output; your review is a separate semantic judgment. "
        "For each analysis, inspect the changed source, predicted dependents, and relevant unpredicted files, "
        "then classify every analyzed file exactly once before running targeted tests."
    ),
)


@mcp.tool()
def analyze_change(files: dict[str, str], changed_files: list[str]) -> dict[str, object]:
    """Create deterministic impact analysis from repository-relative Python source text.

    Provide the captured source files and each changed Python path. This creates an immutable analysis
    snapshot and returns the predicted graph. It does not make a semantic Bob judgment or run tests.
    Use get_analysis_context, submit_bob_impact_review, and run_targeted_tests to finish validation.
    """
    return request_api("POST", "/analyze", {"files": files, "changed_files": changed_files})


@mcp.tool()
def get_analysis_context(analysis_id: str) -> dict[str, object]:
    """Read the exact source snapshot, changed files, prediction, graph, and candidate tests for Bob review.

    Inspect the changed code and relevant predicted and unpredicted files from this snapshot. Do not
    copy the deterministic prediction into Bob's judgment without checking source semantics.
    """
    return request_api("GET", f"/analyses/{analysis_id}/context")


@mcp.tool()
def submit_bob_impact_review(
    analysis_id: str,
    confirmed_files: list[str],
    possible_files: list[str],
    not_affected_files: list[str],
    rationale: str,
) -> dict[str, object]:
    """Record Bob's independently reviewed, complete classification of the analyzed Python files.

    Each file must appear in exactly one list. Confirm every changed file. Use possible_files for
    uncertain semantic relationships; possible impact blocks Safe to Merge until it is resolved.
    Rationale must describe the repository evidence Bob inspected. This does not alter the prediction.
    """
    return request_api(
        "POST",
        f"/analyses/{analysis_id}/bob-review",
        {
            "confirmed_files": confirmed_files,
            "possible_files": possible_files,
            "not_affected_files": not_affected_files,
            "rationale": rationale,
        },
    )


@mcp.tool()
def run_targeted_tests(analysis_id: str) -> dict[str, object]:
    """Execute CodeTwin's predicted tests against this exact snapshot after Bob review is complete.

    Returns actual pytest or unittest results and the resulting merge-gate status. This tool must not
    be described as passing without checking the returned result. Safe to Merge is only set by the
    backend after the required review, analysis, and test checks pass.
    """
    return request_api("POST", f"/analyses/{analysis_id}/run-tests")
