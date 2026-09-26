# CodeTwin Product Specification

## Product

**CodeTwin** is a developer productivity and regression-prevention tool that predicts and validates the downstream impact of a proposed code change before it is merged.

**Tagline:** “Know what your code change will break before it breaks production.”

## Problem

A code change can affect callers, API routes, components, and tests beyond the files directly edited. Reviewers often have to infer those relationships from repository context, and broad test suites can be slow or miss the relevant failure. Developers need a concrete, reviewable account of what a change may affect and evidence from the checks that exercise it.

CodeTwin combines deterministic repository analysis with IBM Bob's repository-aware semantic review and actual targeted test results. It must show which conclusions came from each source.

## Target user

The primary target developer works in an existing repository and needs to understand the downstream impact of a proposed change before merge. Reviewers and maintainers are secondary users. The prototype focuses on Python services and test suites, with a synthetic FastAPI e-commerce repository for the demonstration.

## Current developer workflow

1. A developer edits code on a branch and opens a review or pull request.
2. The developer or reviewer searches imports, callers, APIs, and tests to find likely downstream effects.
3. The developer chooses tests using repository knowledge or runs a broad suite in CI.
4. Reviewers use code review and test results to decide whether to merge; relationships outside the changed files can still be missed.

## CodeTwin workflow

1. A developer selects a repository and proposes a code change.
2. CodeTwin parses the supported Python files and records syntax or analysis errors.
3. CodeTwin builds a deterministic import dependency graph.
4. CodeTwin predicts affected files, functions, classes, API routes, components, and relevant tests.
5. IBM Bob inspects the same proposed snapshot and reviews CodeTwin's prediction using the configured MCP tools.
6. Bob records each analyzed file as **Bob-confirmed impact**, **possible impact**, or **not affected**, with a rationale.
7. CodeTwin runs the tests selected from the predicted impact against the captured snapshot.
8. CodeTwin reports a regression when a targeted test fails; incomplete checks or unresolved possible impact remain visible as blockers.
9. The developer fixes the change and submits a new snapshot for a fresh Bob review and test run.
10. CodeTwin reports **Safe to Merge** only when the required review and validation checks pass.

## Impact terminology

- **Predicted impact** is the deterministic set of changed files and reachable dependents found by repository analysis.
- **Bob-confirmed impact** is Bob's semantic judgment that a file is affected by the change.
- **Possible impact** is Bob's judgment that a file may be affected and needs investigation.
- **Not affected** is Bob's judgment that a file is outside the change's semantic impact. Before Bob review, files outside the predicted graph are only unpredicted; CodeTwin must not present that as Bob's conclusion.
- These sets are displayed separately. Bob's assessment does not rewrite the deterministic prediction.

## Product requirements

### Repository analysis

- Analyze a captured repository snapshot and an explicit set of changed files.
- Use Python AST and deterministic dependency relationships for supported Python analysis.
- Report dependency edges, transitive downstream impact, affected function and class definitions, API files, components, candidate tests, and parse errors.
- Keep analysis reproducible for the same snapshot and changed-file list.
- State the limits of static analysis. In particular, dynamic imports and relationships that are not expressed in analyzed source may be missed.

### IBM Bob validation

- Make IBM Bob an active reviewer through project MCP tools, not just a named feature or documentation reference.
- Give Bob access to the exact captured source snapshot, changed files, prediction, and dependency context for an analysis ID.
- Require Bob to classify all analyzed files once, without overlap, and provide a rationale.
- Keep Bob judgments separate from deterministic output and actual test results.

### Regression validation and merge gate

- Select targeted tests from the deterministic impact graph and execute them against the captured snapshot.
- Show the test files, execution status, and useful output.
- A failing targeted test reports **Regression detected**.
- Missing targeted tests, test execution errors or timeouts, parse errors, missing Bob review, or unresolved possible impact cannot produce **Safe to Merge**.

### Fix & Validate

- A fix is captured as a new analysis revision linked to the failed revision.
- Run deterministic analysis, Bob review, and targeted tests again against the new snapshot.
- Preserve the earlier regression and its test output as evidence.

### Safe to Merge

- Report **Safe to Merge** only after Bob's review is complete, possible impact is resolved, required analysis checks pass, and every selected test passes.
- A prediction or Bob's review alone cannot open the merge gate.

### User interface

- Show the repository, proposed change, an **Analyze Impact** action, predicted impact graph, affected files/APIs/tests, Bob validation, regression status, test results, a **Fix & Validate** action, and current merge-gate status in one review flow.
- Clearly label deterministic predictions separately from Bob's semantic judgments.
- Never display **Safe to Merge** based only on a prediction or an LLM response.

## Demo scenario

The demo uses a synthetic FastAPI e-commerce repository with authentication, users, products, orders, payments, notifications, API routes, services, repositories, and tests. The original payment flow transitions `pending → completed`. The proposed change transitions `pending → authorized → completed`, while a downstream notification component still assumes that `completed` follows `pending` directly. A deterministic workflow test catches the stale assumption. After the developer applies a fix, CodeTwin creates a new revision, Bob reviews it again, and the targeted test must pass before the revision can be called safe to merge.

## Evaluation and success metrics

Evaluate the prototype with the synthetic repository, whose affected files and deliberate regression are known in advance. Report observed results from executed checks; do not claim production accuracy from this fixture.

- **Determinism:** repeated analysis of the same snapshot and changed-file list returns identical graph and impact data.
- **Fixture path coverage:** tests assert that the seeded payment change reaches its downstream notification, checkout/API, and test files.
- **Bob review completeness:** the review accepts complete, non-overlapping classifications and displays them separately from predictions.
- **Regression detection:** the deliberate workflow change produces an actual failing targeted test.
- **Fix validation:** the corrected revision can reach **Safe to Merge** only after a fresh Bob review and passing targeted tests.
- **Fail-closed behavior:** missing or failed required checks never produce **Safe to Merge**.

## Future work

- Evaluate the analyzer against additional repositories with reviewed impact labels before setting accuracy targets.
- Improve static relationships for class inheritance, framework conventions, and other Python constructs.
- Add repository-provider and pull-request integrations only after the local review workflow is validated.
- Consider persistent session storage if deployment or concurrent use requires sessions to survive restarts.

## Non-goals

- Authentication, billing, multi-tenancy, or deployment complexity such as Kubernetes for CodeTwin.
- Unnecessary microservices or databases.
- Large RAG pipelines, custom machine-learning models, or claims that LLM judgments are deterministic.
- Replacing code review, CI, or a repository's full test suite.

## Limitations

- Static analysis can miss dynamic imports, reflection, generated code, runtime plugin loading, and relationships not expressed in parsed source.
- Class definitions are listed from predicted files as a conservative file-level signal; the analyzer does not resolve arbitrary inheritance or runtime dispatch.
- API identification and test selection follow supported syntax and repository conventions, so framework behavior outside those patterns may be missed.
- IBM Bob's semantic review is a model judgment that can vary. It is not deterministic evidence and does not replace tests.
- Targeted tests validate only the captured snapshot and selected tests; they do not replace the repository's full CI suite.
- Analysis sessions are held in process memory and are lost when the backend restarts.

## Deployment requirements

- The React and TypeScript frontend must build for Vercel.
- The FastAPI backend must build and run on Render, expose `GET /health`, and allow the configured deployed frontend origin through CORS.
- API and frontend URLs must come from environment configuration; production code must not depend on a hardcoded localhost URL.
- The public Render demo runs with `CODETWIN_DEMO_ONLY=true`, which restricts source submission and test execution to the checked-in synthetic payment scenario. Local development keeps generic repository analysis enabled by default.
- The final README must contain the public Live Demo URL and local run instructions.

## Git workflow

- Work in small, reviewable stages and keep each commit focused on one stage.
- Before each commit, inspect `git status`, run the relevant validation, inspect the diff, and run `git diff --check`.
- Use conventional commit messages. Do not commit secrets, credentials, `.env` files, dependency directories, virtual environments, or temporary artifacts.
- Do not push unless the user explicitly asks.
