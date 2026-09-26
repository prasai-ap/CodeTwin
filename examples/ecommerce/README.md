# Synthetic e-commerce repository

This FastAPI shop is a deterministic, in-memory demo fixture. All users and products are synthetic; it uses no external account, data source, credentials, or database.

The passing baseline payment flow transitions `pending → completed` and emits a `payment_completed` notification. `scenarios/payment_authorization_regression.patch` inserts an `authorized` transition. The notification consumer still expects the old direct transition, so the payment-workflow test fails because no completion notification is sent. `scenarios/payment_notification_fix.patch` updates the consumer to accept the authorized path.

Install and run from this directory:

```powershell
python -m pip install -r requirements-dev.txt
python -m uvicorn app.main:app --reload
```

Run the baseline checks:

```powershell
python -m pytest -q
```

Reproduce the deliberate regression without changing the checked-in baseline:

```powershell
python -B scripts/reproduce_payment_regression.py
```
