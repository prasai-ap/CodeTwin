from app.database import db
from app.models.order import Order


class OrdersRepository:
    def create(self, user_id: str, product_id: str, quantity: int, total_cents: int) -> Order:
        db.order_sequence += 1
        order = Order(f"order-{db.order_sequence:04d}", user_id, product_id, quantity, total_cents)
        db.orders[order.order_id] = order
        return order

    def get(self, order_id: str) -> Order | None:
        return db.orders.get(order_id)

    def save(self, order: Order) -> Order:
        db.orders[order.order_id] = order
        return order

    def list_for_user(self, user_id: str) -> list[Order]:
        return [order for order in db.orders.values() if order.user_id == user_id]
