"""Payment capture service consumed by order checkout."""

from app.repositories.payments import create_payment


def capture_payment(order_id: str, amount_cents: int) -> dict[str, object]:
    if amount_cents <= 0:
        raise ValueError("Payment amount must be positive")
    return create_payment(order_id=order_id, amount_cents=amount_cents)
