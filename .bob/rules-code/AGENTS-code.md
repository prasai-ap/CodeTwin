# CodeTwin impact review

For a CodeTwin demo payment regression review:

1. Start the CodeTwin API, then create the demo analysis in the UI or with `POST /demo/payment-regression`. Do not edit the checked-in e-commerce baseline.
2. Call `codetwin.get_analysis_context` with the returned `analysis_id`. This returns the exact proposed snapshot, deterministic prediction, targeted tests, and session status.
3. Inspect the changed payment implementation, every predicted dependent, and the payment workflow test. Decide which files Bob confirms are semantically affected, which could be affected, and which are not affected. Consider payment amount units, order totals, API behavior, and notification behavior.
4. Call `codetwin.submit_bob_impact_review` with the same analysis ID and three disjoint lists that classify every Python file in the snapshot exactly once. Explain the reasoning in `rationale`.
5. Call `codetwin.run_targeted_tests` with the same analysis ID. Report the test output and final status from CodeTwin; do not claim Safe to Merge if a test failed or possible impact remains unresolved.

For a repository that is not using the CodeTwin UI, Bob can instead call `codetwin.analyze_change` with the source snapshot and changed paths to create an analysis session.

CodeTwin's AST prediction is deterministic. Bob's semantic classifications are separate agent judgments. Never describe the change as safe to merge based on the Bob review alone; the targeted tests must also pass.
