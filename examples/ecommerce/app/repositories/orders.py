from dataclasses import replace

from app.database import db
from app.models import Order


class OrdersRepository:
    def create(self, user_id: str, product_id: str, quantity: int, total_cents: int) -> Order:
        db.order_sequence += 1
        order = Order(f"order-{db.order_sequence}", user_id, product_id, quantity, total_cents)
        db.orders[order.order_id] = order
        return order

    def get(self, order_id: str) -> Order | None:
        return db.orders.get(order_id)

    def complete(self, order_id: str) -> Order:
        order = db.orders[order_id]
        updated = replace(order, status="completed")
        db.orders[order_id] = updated
        return updated
