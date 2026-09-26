# AGENTS.md — Plan mode architecture rules

This file provides guidance to agents when working with code in this repository.

## Non-obvious architectural constraints

- **Evidence separation is a first-class design principle**: predicted impact (AST), Bob-confirmed impact (semantic), and test results must remain independent evidence layers. Any feature that merges these three into a single status before the merge gate would violate the core design.
- **In-memory session store is intentional for the prototype**, not a known gap. `analysis_store.py` uses `threading.RLock` for concurrency. Persisting sessions would require an explicit design decision.
- **`safe_to_merge` is computed server-side only** — the frontend reads the field from the API response and never infers it independently. Do not move merge-gate logic into the frontend.
- **Snapshot immutability**: once a session is created, its snapshot (`_snapshots[analysis_id]`) is never mutated. A correction creates a new session with a `parent_analysis_id` pointer. The old failed session remains inspectable.
- **`CODETWIN_DEMO_ONLY=true`** on Render gates `/analyze` (generic submissions) but leaves all `/demo/*` and `/analyses/*` routes open. Any new general-purpose route must check `demo_only` if source submission is involved.
- **Frontend polling model**: `App.tsx` polls `GET /analyses/{id}` while status is `awaiting_bob_review` or `awaiting_tests`. Adding new transitional statuses to `AnalysisStatus` in `types.ts` requires updating the polling condition in `App.tsx`.
- **No path aliases or monorepo tooling**: backend and frontend are fully independent projects with separate dependency manifests. There is no shared package or symlink between them.
- **MCP server is a stdio child process** — it cannot be deployed as a web service. It must be launched by Bob locally via `.bob/mcp.json` and communicates with the API over the configured `CODETWIN_API_BASE_URL`.
