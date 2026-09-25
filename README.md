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

`POST /demo/payment-regression` creates an analysis session from the synthetic e-commerce checkout regression. It applies the demo patch to an in-memory snapshot, leaving the checked-in baseline unchanged.

Install `requirements-dev.txt` to run the test suite with pytest. It includes the MCP SDK used by the IBM Bob integration. The tests also work with Python's built-in test runner:

```powershell
python -B -m unittest discover -s tests -v
```

## IBM Bob review

Open this project in IBM Bob and keep the FastAPI service running. Create an analysis with the demo endpoint or UI, then ask Bob to review its analysis ID. The project MCP server in `.bob/mcp.json` exposes `get_analysis_context`, `submit_bob_impact_review`, and `run_targeted_tests` for that same session. Bob inspects the proposed snapshot and its predicted dependents, then returns disjoint lists for Bob-confirmed impact, possible impact, and files not affected. Bob then asks CodeTwin to run the targeted tests. The API keeps Bob's judgment separate from the AST prediction. `analyze_change` remains available when Bob starts an analysis directly from a source snapshot.

The demo sessions are held in memory and reset when the API restarts. After Bob reviews the impact, call `POST /analyses/{analysis_id}/run-tests`; CodeTwin runs only the predicted tests from the captured snapshot in a temporary directory. It prefers pytest and falls back to unittest for the self-contained demo. A failed test reports `regression_detected`. CodeTwin reports `safe_to_merge` only when Bob has no unresolved possible impact, there are no Python parse errors, and every targeted test passes.

The analyzer is deterministic and import based. Bob's semantic classifications are agent judgments and are not presented as deterministic analysis.
