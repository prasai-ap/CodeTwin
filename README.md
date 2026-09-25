# CodeTwin

Know what your code change will break before it breaks production.

CodeTwin predicts downstream impact from deterministic repository analysis, validates that impact with IBM Bob, and runs the relevant tests before it can report a change as safe to merge.

## Backend analyzer

The first backend slice builds a Python import dependency graph and reports changed files, their transitive dependents, impacted API files, targeted tests, and files outside the predicted impact.

Run the API from the `backend` directory:

```powershell
python -m pip install -r requirements.txt
python -m uvicorn codetwin.api:app --reload
```

The API is available at `http://127.0.0.1:8000`; interactive docs are at `/docs`. `GET /health` checks the service. `POST /analyze` accepts a repository snapshot as a mapping of relative paths to file contents and a list of changed Python files. It does not read arbitrary paths from the server filesystem.

Install `requirements-dev.txt` to run the test suite with pytest. It includes the MCP SDK used by the IBM Bob integration. The tests also work with Python's built-in test runner:

```powershell
python -B -m unittest discover -s tests -v
```

## IBM Bob review

Open this project in IBM Bob and keep the FastAPI service running. The project MCP server in `.bob/mcp.json` exposes `analyze_change` and `submit_bob_impact_review`. Bob receives the deterministic prediction and source snapshot, inspects the proposed change and its dependents, then returns disjoint lists for Bob-confirmed impact, possible impact, and files not affected. The API keeps Bob's judgment separate from the AST prediction.

The demo sessions are held in memory and reset when the API restarts. A Bob review moves an analysis to `awaiting_tests`; it cannot set `safe_to_merge`. Targeted test execution and final merge gating remain to be implemented.

The analyzer is deterministic and import based. Bob's semantic classifications are agent judgments and are not presented as deterministic analysis.
