"""IBM Bob MCP tools that connect semantic review to CodeTwin's API."""

from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from mcp.server.fastmcp import FastMCP

API_URL = os.environ.get("CODETWIN_API_URL", "http://127.0.0.1:8000").rstrip("/")
mcp = FastMCP("CodeTwin")


def _post(path: str, payload: dict[str, object]) -> dict[str, object]:
    request = Request(
        f"{API_URL}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise ValueError(f"CodeTwin API returned HTTP {error.code}: {detail}") from error
    except URLError as error:
        raise ValueError(f"CodeTwin API is unavailable at {API_URL}; start the FastAPI service first") from error


@mcp.tool()
def analyze_change(files: dict[str, str], changed_files: list[str]) -> dict[str, object]:
    """Create a deterministic CodeTwin prediction for Python files Bob read from the open repository.

    Pass a mapping of repository-relative Python paths to their full source text and the changed
    Python paths. The result includes the deterministic dependency prediction and an analysis ID
    that Bob must use when it submits its separate semantic review.
    """
    analysis = _post("/analyses", {"files": files, "changed_files": changed_files})
    analysis["review_snapshot"] = files
    return analysis


@mcp.tool()
def submit_bob_impact_review(
    analysis_id: str,
    confirmed_files: list[str],
    possible_files: list[str],
    not_affected_files: list[str],
    rationale: str,
) -> dict[str, object]:
    """Record IBM Bob's repository-aware semantic classifications for a CodeTwin analysis.

    Classify every Python file from the analysis exactly once: Bob-confirmed downstream impact,
    possible impact that needs investigation, or not affected. CodeTwin retains its deterministic
    predictions separately and still requires actual tests before it can mark anything merge safe.
    """
    return _post(
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
    """Execute CodeTwin's predicted tests after Bob completes its semantic impact review.

    Returns the real targeted test results and merge-gate status. A failed test reports a
    regression; unresolved possible impact or parse errors also prevent Safe to Merge.
    """
    return _post(f"/analyses/{analysis_id}/run-tests", {})


if __name__ == "__main__":
    mcp.run(transport="stdio")
