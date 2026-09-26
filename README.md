# CodeTwin

> Know what your code change will break before it breaks production.

CodeTwin predicts the downstream impact of a proposed code change, asks IBM Bob to validate the semantic impact, and runs targeted tests before reporting merge readiness.

**Live Demo:** Pending public deployment.

## Product

See [PRODUCT_SPEC.md](PRODUCT_SPEC.md) for the problem, target user, workflow, requirements, demo scenario, and non-goals.

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for the system design, analysis boundaries, IBM Bob workflow, testing strategy, and repository structure.

## Repository layout

The initial backend, frontend, and synthetic e-commerce example layout is documented in [ARCHITECTURE.md](ARCHITECTURE.md#initial-repository-structure).

## Development

### Backend

From `backend/`, install the backend and Bob MCP dependencies, then start the API:

```sh
python -m pip install -r requirements-dev.txt
python -m uvicorn codetwin.api:app
```

### Frontend

From `frontend/`, install the locked dependencies, create `.env.local`, and set `VITE_API_BASE_URL` to the origin of the running CodeTwin API:

```sh
npm ci
npm run dev
```

## Validation

Run backend tests from `backend/` with `python -m pytest -q tests`. Run the frontend TypeScript check and production build from `frontend/` with `npm run build`.

## IBM Bob

CodeTwin registers a project-scoped stdio MCP server in `.bob/mcp.json` and provides review instructions in `.bob/rules-code/`. The MCP adapter calls the same FastAPI service as the dashboard.

Before opening the project in IBM Bob, set `CODETWIN_API_BASE_URL` in the environment used to launch Bob to the origin of the running CodeTwin API. In Bob's MCP settings, enable the `codetwin` server. Its tools are not auto-approved by project configuration.

Bob's review flow is: inspect the analysis snapshot with `get_analysis_context`, independently classify all analyzed files with `submit_bob_impact_review`, then run `run_targeted_tests`. For a repository Bob is analyzing directly, start with `analyze_change`. Details are in the [architecture guide](ARCHITECTURE.md#ibm-bob-validation-workflow).
