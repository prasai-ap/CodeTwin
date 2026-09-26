# CodeTwin

> Know what your code change will break before it breaks production.

CodeTwin builds a deterministic impact map from Python imports and calls, asks IBM Bob to independently inspect that map against the captured source, and runs targeted tests before it reports merge readiness.

**Live Demo:** Pending deployment. See [Deployment](#deployment).

## What the prototype demonstrates

- A React and TypeScript developer dashboard with a downstream dependency graph, affected files, APIs, components, and tests.
- Python AST analysis that predicts impact without using an LLM.
- IBM Bob as a repository-aware reviewer through project-scoped MCP tools. Bob classifies files as confirmed, possible, or not affected.
- A server-side merge gate that reports **Safe to Merge** only after Bob review is complete and all targeted tests pass.
- A synthetic FastAPI e-commerce payment regression: `pending → completed` changes to `pending → authorized → completed`, while notifications still assume the old transition. The targeted test fails until the notification consumer is fixed and the new snapshot is revalidated.

All repository and transaction data in the demo are synthetic.

## Local development

Use Python 3.10 or newer and Node.js 20 or newer.

### Start the backend

From `backend/`, install the development dependencies, allow the local Vite origin through CORS, and start FastAPI:

```powershell
python -m pip install -r requirements-dev.txt
$env:FRONTEND_ORIGINS = "http://localhost:5173"
$env:CODETWIN_DEMO_ONLY = "false"
python -m uvicorn codetwin.api:app --reload
```

The API is available at `http://localhost:8000`; `GET /health` reports service health. Local generic repository analysis is enabled unless `CODETWIN_DEMO_ONLY=true` is set.

### Start the frontend

From `frontend/`, install the locked dependencies and configure the API origin in `.env.local`:

```text
VITE_API_BASE_URL=http://localhost:8000
```

Then run:

```sh
npm ci
npm run dev
```

The dashboard opens at `http://localhost:5173`. Production builds require `VITE_API_BASE_URL` to be set in the Vercel project environment; the frontend has no built-in API host.

### Connect IBM Bob

The repository includes `.bob/mcp.json` and review guidance in `.bob/rules-code/`. Install backend dependencies, set `CODETWIN_API_BASE_URL` in the environment used to launch IBM Bob to the API origin, then enable the project `codetwin` MCP server in Bob. The server exposes tools to inspect the captured analysis, submit Bob's independent impact classification, and run targeted tests. The project configuration does not auto-approve the tools.

For the public demo, start the payment scenario in the UI, then use the copied Bob review prompt. Bob's MCP process must point to the same Render API origin as the browser. The public service accepts only the built-in synthetic payment scenario and does not enable arbitrary submitted-source test execution.

## Deployment

The repository contains a Render Blueprint at [`render.yaml`](render.yaml) and Vercel settings at [`frontend/vercel.json`](frontend/vercel.json). Both services use the repository root as their source; set the Vercel project root directory to `frontend`.

1. Connect this GitHub repository to Render and create the Blueprint. The API service runs with `CODETWIN_DEMO_ONLY=true`, installs `backend/requirements.txt`, and uses `/health` for its health check. It starts with empty CORS origins until the frontend URL is known.
2. Connect the repository to Vercel with root directory `frontend`. Add `VITE_API_BASE_URL` using the Render API origin and deploy the frontend.
3. Copy the Vercel production origin into the Render service's `FRONTEND_ORIGINS` environment variable, then redeploy the API.
4. Set `CODETWIN_API_BASE_URL` in the environment that launches IBM Bob to the same Render API origin. Open the site, start the payment regression, and use Bob's MCP tools to validate the captured analysis and run tests.
5. After deployment succeeds, replace the pending Live Demo line above with the Vercel production URL.

There are no API credentials in the repository. The demo session store is in process memory, so sessions are temporary and intended for the single-instance hackathon demo.

## Checks

Run the backend suite from `backend/`:

```sh
python -m pytest -q tests
```

Run the frontend type check and production build from `frontend/`:

```sh
npm run build
```

The synthetic fixture also includes a helper to prove that the regression patch fails and the notification fix passes; see `examples/ecommerce/README.md`.

## Project documentation

- [Product specification](PRODUCT_SPEC.md)
- [Architecture](ARCHITECTURE.md)
