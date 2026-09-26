# CodeTwin Project Rules

## Repository Analysis

* Never invent repository structure, files, modules, functions, classes, APIs, tests, or dependency relationships.
* Repository findings must be based on actual repository inspection or deterministic analysis.
* Clearly distinguish observations, assumptions, and uncertainty.

## Deterministic Impact Analysis

* CodeTwin's core repository and impact analysis must remain deterministic.
* Do not replace the deterministic dependency graph with an LLM-generated dependency graph.
* Do not hardcode the expected results of the demo payment scenario.
* Dependency paths must be supported by the actual repository graph.
* Prefer explainable graph traversal and evidence-based relationships.

## Predicted vs Confirmed Impact

Maintain a strict distinction between:

PREDICTED IMPACT

and:

BOB CONFIRMED IMPACT

The deterministic CodeTwin engine produces PREDICTED IMPACT.

IBM Bob independently validates those predictions.

Never describe a CodeTwin prediction as confirmed before Bob has independently inspected the repository.

Use these validation categories where applicable:

* CONFIRMED IMPACT
* POSSIBLE IMPACT
* NOT ACTUALLY AFFECTED
* MISSED IMPACT

## Testing

* Never claim that a test passed unless it was actually executed.
* Never fabricate test output, duration, coverage, or regression results.
* Prefer targeted tests related to the affected dependency path.
* Clearly distinguish static analysis from executed test results.
* If a test has not been executed, explicitly state that it has not been executed.

## Dependency Explanations

When reporting impact, explain:

* affected component
* affected file
* affected function/class when known
* dependency path
* reason for the impact
* relevant tests

Do not report an affected component without evidence.

## Regression Detection

Only report REGRESSION DETECTED when an actual test execution or other explicitly verified execution result demonstrates the regression.

Static analysis alone must not be presented as proof of a regression.

## Fix and Validation

After a fix:

1. Inspect the changed component.
2. Rerun the relevant targeted tests.
3. Rerun impact analysis when appropriate.
4. Verify the dependency path.
5. Confirm the previous failure is resolved.

Do not report SAFE TO MERGE until the required validation has actually been performed.

## Demo Scenario

The synthetic e-commerce demo changes the payment workflow from:

pending -> completed

to:

pending -> authorized -> completed

Do not hardcode the expected impact or regression result.

Use the actual repository and actual test execution.

## IBM Bob Role

IBM Bob is a core semantic validation component of CodeTwin.

Bob should independently inspect the repository and validate CodeTwin's predicted impact.

Bob should identify:

* confirmed impacts
* possible impacts
* unaffected predictions
* missed impacts
* relevant tests
* regression risks
* test gaps

Never claim Bob validated something unless Bob actually inspected the repository.

## Data Integrity

* Use synthetic data only.
* Never introduce personal information, confidential data, client data, credentials, API keys, or secrets.
* Never commit secrets or .env files.

## Change Discipline

* Avoid unrelated changes.
* Preserve the existing architecture unless a change is necessary.
* Prefer small, reviewable modifications.
* Do not silently rewrite unrelated components.

## Structured Reporting

For analysis tasks, prefer structured results containing:

* finding
* evidence
* affected component
* dependency path
* confidence or uncertainty
* relevant tests
* recommended next action

Never fabricate missing information.
