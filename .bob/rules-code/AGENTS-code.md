# CodeTwin impact review

For a CodeTwin demo payment regression review:

1. Read every Python source and test file under `examples/ecommerce/app` and `examples/ecommerce/tests`. Treat paths relative to `examples/ecommerce` when calling CodeTwin.
2. Build the proposed snapshot by applying the change in `examples/ecommerce/scenarios/payment_amount_regression.patch` to `app/payments/service.py` in memory. Do not edit the checked-in baseline fixture.
3. Call the `codetwin.analyze_change` MCP tool with that Python file snapshot and `changed_files=["app/payments/service.py"]`. Preserve the returned `analysis_id`.
4. Inspect the changed payment implementation, every predicted dependent, and the payment workflow test. Decide which files Bob confirms are semantically affected, which could be affected, and which are not affected. Consider payment amount units, order totals, API behavior, and notification behavior.
5. Call `codetwin.submit_bob_impact_review` with the analysis ID and three disjoint lists that classify every Python file in the snapshot exactly once. Explain the reasoning in `rationale`.

CodeTwin's AST prediction is deterministic. Bob's semantic classifications are separate agent judgments. Never describe the change as safe to merge based on the Bob review alone; the targeted tests must also pass.
