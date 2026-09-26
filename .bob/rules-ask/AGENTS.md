# AGENTS.md — Ask mode context rules

This file provides guidance to agents when working with code in this repository.

## Non-obvious context

- **`examples/ecommerce/`** is a synthetic fixture, not a real application — it exists solely to demonstrate the regression/fix demo scenario. The checked-in files are always the passing baseline; the API applies patches to in-memory snapshots.
- **Two separate "impact" concepts**: *predicted impact* (deterministic AST output from `analyzer.py`) and *Bob-confirmed impact* (semantic judgment). They are stored and displayed separately; never conflate them.
- **Session state is ephemeral**: all analysis sessions live in `analysis_store._sessions` (process memory). No database, no file persistence. A restart wipes everything.
- **`ARCHITECTURE.md`** is the authoritative design reference — it describes component boundaries, the evidence-separation principle, and the merge-gate conditions precisely. Prefer it over README for technical questions.
- **`.bob/rules-code/codetwin-impact-validation.md`** defines the step-by-step Bob review workflow that Bob itself should follow when validating a proposed change using the CodeTwin MCP tools.
- **`demo-project/` and `tests/` at repo root** are intentionally empty stubs (`.gitkeep` only) reserved for future expansion.
