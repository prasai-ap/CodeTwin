# CodeTwin

> Know what your code change will break before it breaks production.

## Problem

Changes can affect callers, APIs, classes, and tests beyond the edited files. Reviewers need repository context to find those relationships, while broad test runs can be slow or miss a focused regression.

## Solution

CodeTwin combines deterministic Python repository analysis, an impact graph, IBM Bob's independent semantic review, and targeted test execution. It keeps those evidence sources separate and reports **Safe to Merge** only after required validation passes.

## Architecture overview

The React, TypeScript, and Vite frontend submits a proposed snapshot to a FastAPI backend. Python AST analysis and dependency traversal predict impact. IBM Bob reviews the same snapshot through project MCP tools. A test runner executes selected tests against that snapshot.

See [ARCHITECTURE.md](ARCHITECTURE.md) for component boundaries and data flow, and [PRODUCT_SPEC.md](PRODUCT_SPEC.md) for requirements and limitations.

## Current status

The repository already contains an MVP and a synthetic e-commerce fixture from earlier implementation stages. This foundation stage documents the requested project layout; it does not add application behavior. Public deployment is not yet available.

## Planned workflow

1. Developer proposes a repository change.
2. CodeTwin deterministically analyzes Python source and builds an impact graph.
3. CodeTwin predicts affected files, functions, classes, APIs, components, and tests.
4. IBM Bob independently inspects the source and validates the predicted impact.
5. CodeTwin executes targeted tests and reports their actual results.
6. After a regression, the developer fixes the change and repeats analysis, Bob review, and testing.
7. CodeTwin reports **Safe to Merge** only when required reviews and checks pass.
