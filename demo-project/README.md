# Synthetic E-commerce Demo

This is a small FastAPI repository used to exercise CodeTwin's repository-impact workflow. It contains only synthetic users, products, and orders, held in memory for each process.

The checked-in baseline follows the original payment workflow: `pending → completed`. A developer can create an order, then complete its pending payment. Completion updates the order and sends a notification through the service dependency path:

`Payment API → Payment Service → Order Service → Notification Service`

## Run locally

From this directory, install the small development dependency set and start the API:

```shell
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

Run the baseline suite with:

```shell
python -m pytest -q
```

The API seeds two synthetic demo users and two synthetic products. Use `X-Demo-User: user-ada` or `X-Demo-User: user-grace` on user-specific requests. Data resets when the process restarts.
