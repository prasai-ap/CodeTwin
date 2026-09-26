"""FastAPI entry point for the synthetic store."""

from fastapi import FastAPI

from app.api import auth, notifications, orders, payments, products, users

app = FastAPI(title="CodeTwin Synthetic Shop", version="0.1.0")

for router in (auth.router, users.router, products.router, orders.router, payments.router, notifications.router):
    app.include_router(router)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}
