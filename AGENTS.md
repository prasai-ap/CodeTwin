# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## Stack

- **Backend**: Python 3.13, FastAPI, pytest — lives in `backend/`
- **Frontend**: TypeScript, React 19, Vite — lives in `frontend/`
- **MCP server**: stdio process launched by IBM Bob via `.bob/mcp.json`, entry point `backend/run_bob_mcp.py`

## Commands

### Backend (run from repo root — pytest must resolve `codetwin.*` imports)

```sh
# Install dev dependencies (creates venv if needed)
cd backend && pip install -r requirements-dev.txt

# Run all backend tests
cd backend && python -m pytest tests/

# Run a single test file
cd backend && python -m pytest tests/test_analyzer.py

# Run a single test by name
cd backend && python -m pytest tests/test_analyzer.py::test_analysis_is_deterministic_and_reports_transitive_python_dependencies

# Start the API server for local dev
uvicorn codetwin.api:app --app-dir backend --reload
```

### Frontend (run from `frontend/`)

```sh
npm run dev          # dev server
npm run build        # tsc -b && vite build (type-check + bundle)
```

## Critical env vars

| Variable | Where set | Purpose |
|---|---|---|
| `VITE_API_BASE_URL` | `frontend/.env` (gitignored) | Backend origin for the frontend; **no fallback** — build fails silently if blank |
| `FRONTEND_ORIGINS` | backend process env | Comma-separated CORS allowed origins |
| `CODETWIN_API_BASE_URL` | backend process env | Origin the MCP adapter (`api_client.py`) calls; **no built-in fallback** |
| `CODETWIN_DEMO_ONLY=true` | set on Render | Blocks `/analyze` with 403; only demo routes work |

## Architecture gotchas

- **Session store is in-process memory** (`analysis_store.py`): restarting the backend clears all sessions. The frontend has no persistence.
- **MCP process is separate from FastAPI**: `run_bob_mcp.py` is a child stdio process; it communicates to the API over HTTP via `api_client.py`, not in-memory. Both the UI and Bob read/write the same API session.
- **`create_app()` factory**, not a module-level `app`: tests must call `create_app()` with `frontend_origins=` to configure CORS. Production uses `codetwin.api:app` (Uvicorn calls `create_app()` via a module-level `app = create_app()` implied by the import).
- **Bob must classify every analyzed file exactly once** before `submit_bob_impact_review` succeeds. Files must cover `predicted_impact.files + not_affected` with no overlaps and no omissions.
- **`safe_to_merge: true`** requires: Bob review complete, zero possible-impact files, zero parse errors, ≥1 selected test, all selected tests passing.
- **Demo-only mode** applies the regression/fix to in-memory snapshots; it does not edit `examples/ecommerce/` fixture files.

## Code style

### Python
- All modules start with `from __future__ import annotations`
- Domain models use `@dataclass(frozen=True)` (see `analysis_models.py`); `.to_dict()` via `dataclasses.asdict`
- Internal imports use `from codetwin.<module> import ...` (absolute, never relative)
- No type: ignore comments; full type annotations on all public functions

### TypeScript
- `verbatimModuleSyntax: true` — use `import type` for type-only imports (enforced by compiler)
- `noUnusedLocals` and `noUnusedParameters` are errors
- All API shapes live in `frontend/src/types.ts`; `api.ts` is the only fetch layer

## Git workflow (from ARCHITECTURE.md)
Run `git diff --check` before committing. Implement one reviewable stage at a time. Do not push unless the user explicitly requests it.
