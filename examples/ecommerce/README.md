# Synthetic e-commerce repository

This small FastAPI service is the CodeTwin demo target. It contains authentication, users, products, orders, payments, notifications, in-memory repositories, and workflow tests. Its in-memory store keeps the demo self-contained; it does not require a database service.

Run the API from this directory with `python -m uvicorn app.main:app --reload`. The demo user is selected with the `X-User-ID: user-1` request header. This is a fixture for demonstrating dependency analysis, not production authentication.

Run its passing baseline tests with `python -B -m unittest discover -s tests -v`.

## Deliberate payment regression

`scenarios/payment_amount_regression.patch` changes the payment repository write from cents to whole currency units while leaving the field named `amount_cents`. Run `python -B scripts/reproduce_payment_regression.py` to apply the proposed change in a temporary copy and execute the targeted workflow test. The test detects that the captured payment is one hundred times too small. The changed payment service is imported by the order service, checkout route, and workflow tests, giving CodeTwin a concrete impact chain to predict.
