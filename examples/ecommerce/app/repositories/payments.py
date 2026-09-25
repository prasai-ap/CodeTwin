from app import database


def create_payment(order_id: str, amount_cents: int) -> dict[str, object]:
    payment_id = f"payment-{database.state['next_payment_id']}"
    database.state["next_payment_id"] += 1
    payment = {
        "id": payment_id,
        "order_id": order_id,
        "amount_cents": amount_cents,
        "status": "captured",
    }
    database.state["payments"][payment_id] = payment
    return payment


def get_payment(payment_id: str) -> dict[str, object] | None:
    return database.state["payments"].get(payment_id)
