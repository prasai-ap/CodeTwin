# AGENTS.md — Agent mode coding rules

This file provides guidance to agents when working with code in this repository.

## Non-obvious coding rules

- **`from __future__ import annotations`** must be the first import in every new Python module — the entire backend depends on it for forward-reference resolution.
- **`create_app()` factory pattern**: never add a module-level `app = FastAPI(...)` directly; always use/extend `create_app()` in `backend/codetwin/api.py` so tests can pass `frontend_origins=` without environment vars.
- **`analysis_store` is the single source of truth** for session state — never let `api.py` or `bob_mcp.py` mutate session dicts directly. All writes go through `analysis_store.py` functions which hold `_lock` (RLock).
- **Bob review completeness is enforced at submission**: `confirmed_files + possible_files + not_affected_files` must equal `predicted_impact.files + not_affected` exactly (no gaps, no duplicates). Tests in `test_api.py` use `_classify_every_file()` helper to compute this set.
- **MCP tools call the HTTP API**, not Python functions directly — `bob_mcp.py` imports only `api_client.request_api`. Do not add direct calls to `analysis_store` from `bob_mcp.py`.
- **`CODETWIN_API_BASE_URL` has no fallback** in `api_client.py` — if unset, every MCP tool call will raise immediately. Always set it when running the MCP server outside of tests.
- **TypeScript `import type`** is required for all type-only imports (`verbatimModuleSyntax: true`). The build will fail otherwise.
- **Frontend has no test runner** — validation is `npm run build` (which runs `tsc -b` first). There are no vitest/jest tests; TypeScript type errors are the CI gate.
- **Backend tests must run from `backend/` directory** so that `codetwin.*` resolves as a top-level package. Running `pytest` from repo root will fail with import errors.

## MCP server (CodeTwin tool)

Bob has the `codetwin` MCP server available. Use it when reviewing impact or running targeted tests:
- `analyze_change` — create a new analysis from source files
- `get_analysis_context` — load an existing session's full snapshot
- `submit_bob_impact_review` — record complete file classifications
- `run_targeted_tests` — execute predicted tests against the snapshot
