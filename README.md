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

Install `requirements-dev.txt` to run the test suite with pytest. The tests also work with Python's built-in test runner:

```powershell
python -B -m unittest discover -s tests -v
```

The current analyzer is deterministic and import based. IBM Bob semantic validation and execution of targeted tests will be added in later implementation stages; this slice does not claim that a change is safe to merge.
