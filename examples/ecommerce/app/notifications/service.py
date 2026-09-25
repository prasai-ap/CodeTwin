"""Notification orchestration for order events."""

from app.repositories.notifications import add_notification


def send_order_confirmation(user_id: str, order_id: str) -> dict[str, str]:
    return add_notification(user_id, order_id, "Your order was paid and confirmed.")
