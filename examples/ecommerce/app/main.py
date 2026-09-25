"""FastAPI entry point for the synthetic e-commerce repository."""

from fastapi import FastAPI

from app.routes import auth, notifications, orders, payments, products, users

app = FastAPI(title="CodeTwin Demo Shop", version="1.0.0")
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(products.router)
app.include_router(orders.router)
app.include_router(payments.router)
app.include_router(notifications.router)
