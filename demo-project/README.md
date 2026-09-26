# Synthetic E-commerce Demo

This is a small FastAPI repository used to exercise CodeTwin's repository-impact workflow. It contains only synthetic users, products, and orders, held in memory for each process.

The demo now follows the proposed payment workflow: `pending → authorized → completed`. A developer can create an order, then complete its pending payment. The payment and order complete, but the notification service still assumes the original direct transition, so the completion notification is missing:

`Payment API → Payment Service → Order Service → Notification Service`

See [`docs/demo-scenario.md`](../docs/demo-scenario.md) for the intended regression and failing test.

## Run locally

From this directory, install the small development dependency set and start the API:

```shell
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

Run the suite with:

```shell
python -m pytest -q
```

The suite intentionally has one failing regression test until the downstream notification assumption is fixed.

The API seeds two synthetic demo users and two synthetic products. Use `X-Demo-User: user-ada` or `X-Demo-User: user-grace` on user-specific requests. Data resets when the process restarts.
