"""Order state transitions for the original payment workflow."""

from dataclasses import replace

from app.models.order import Order, OrderStatus


def complete_order(order: Order) -> Order:
    if order.status is not OrderStatus.PENDING:
        raise ValueError("Only pending orders can be completed")
    return replace(order, status=OrderStatus.COMPLETED)
