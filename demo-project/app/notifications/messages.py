"""Human-readable messages for store events."""

from app.models.order import Order


def payment_completed_message(order: Order) -> str:
    return f"Payment for order {order.order_id} is complete."
