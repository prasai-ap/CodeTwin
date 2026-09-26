# CodeTwin Product Specification

## Product

**CodeTwin** is a developer productivity and regression-prevention tool that predicts and validates the downstream impact of a proposed code change before it is merged.

**Tagline:** “Know what your code change will break before it breaks production.”

## Problem

A code change can affect callers, API routes, components, and tests beyond the files directly edited. Reviewers often have to infer those relationships from repository context, and broad test suites can be slow or miss the relevant failure. Developers need a concrete, reviewable account of what a change may affect and evidence from the checks that exercise it.

CodeTwin combines deterministic repository analysis with IBM Bob's repository-aware semantic review and actual targeted test results. It must show which conclusions came from each source.

## Target user

The primary user is a software developer or reviewer working in an existing repository who needs to assess a proposed change before merge. The prototype focuses on Python services and test suites, with a synthetic FastAPI e-commerce repository for the demonstration.

## User workflow

1. A developer supplies a repository snapshot and the changed files.
2. CodeTwin parses the supported Python files and records syntax or analysis errors.
3. CodeTwin builds a deterministic import dependency graph.
4. CodeTwin predicts downstream files, API routes, components, and relevant tests.
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
- Report dependency edges, transitive downstream impact, API files, components, candidate tests, and parse errors.
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
- Report **Safe to Merge** only after Bob's review is complete, possible impact is resolved, required analysis checks pass, and every selected test passes.
- A fix is a new analysis revision with fresh review and test evidence; preserve the failed revision as evidence.

### User interface

- Show the change, predicted impact graph, Bob classifications, targeted test evidence, and current merge-gate status in one review flow.
- Clearly label deterministic predictions separately from Bob's semantic judgments.
- Never display **Safe to Merge** based only on a prediction or an LLM response.

## Demo scenario

The demo uses a synthetic FastAPI e-commerce repository with authentication, users, products, orders, payments, notifications, API routes, repositories, and tests. A deliberate payment change divides a value already expressed in cents by 100. The order workflow test catches the amount mismatch. After the developer applies the fix, CodeTwin creates a new revision, Bob reviews it again, and the targeted test must pass before the revision can be called safe to merge.

## Success criteria

- Repeated analysis of the same snapshot produces the same graph and predicted impact.
- The demo graph reaches the downstream checkout/API/test files from the payment change.
- Bob's classifications are complete, disjoint, and visibly distinct from predictions.
- The deliberate regression is caught by an executed targeted test.
- The corrected revision can reach **Safe to Merge** only after fresh Bob review and passing targeted tests.
- A failed or incomplete check always keeps the merge gate closed.

## Non-goals

- Authentication, billing, multi-tenancy, Kubernetes, or deployment infrastructure for CodeTwin.
- Unnecessary microservices or databases.
- Large RAG pipelines, custom machine-learning models, or claims that LLM judgments are deterministic.
- Replacing code review, CI, or a repository's full test suite.

## Git workflow

- Work in small, reviewable stages and keep each commit focused on one stage.
- Before each commit, inspect `git status`, run the relevant validation, inspect the diff, and run `git diff --check`.
- Use conventional commit messages. Do not commit secrets, credentials, `.env` files, dependency directories, virtual environments, or temporary artifacts.
- Do not push unless the user explicitly asks.
