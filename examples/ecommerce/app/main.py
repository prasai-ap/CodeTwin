"""FastAPI application for CodeTwin's synthetic e-commerce example."""

from fastapi import FastAPI

from app.routes import auth, notifications, orders, payments, products, users

app = FastAPI(title="CodeTwin Synthetic Shop", version="0.1.0")
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(products.router)
app.include_router(orders.router)
app.include_router(payments.router)
app.include_router(notifications.router)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}
