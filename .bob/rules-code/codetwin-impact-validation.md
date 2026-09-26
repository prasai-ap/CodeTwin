# CodeTwin impact validation workflow

When reviewing a proposed repository change with CodeTwin:

1. Use the CodeTwin MCP tools as an active part of the review. For an existing UI/API analysis, call `get_analysis_context` with its analysis ID. Otherwise, inspect the relevant repository files and call `analyze_change` with their source text and changed paths.
2. Independently inspect the changed code, the predicted files, functions, classes, API routes and tests, plus relevant files outside the predicted graph. Treat the AST result as deterministic prediction evidence, not as proof of semantic impact.
3. Call `submit_bob_impact_review` only after classifying every analyzed file exactly once as Bob-confirmed impact, possible impact, or not affected. Confirm each changed file, explain the source evidence in the rationale, and use possible impact when uncertain.
4. Call `run_targeted_tests` after the review. Report the actual returned test status and output.
5. Do not claim Safe to Merge unless CodeTwin returns `safe_to_merge: true` after the review and tests. Any unresolved possible impact or failed, missing, or incomplete check keeps the gate closed.
6. After a fix, inspect the new snapshot and repeat Bob review and targeted validation for its new analysis ID.

Keep Bob's semantic findings separate from CodeTwin's deterministic predicted impact and executed test results. Never claim that Bob's judgment is deterministic.
