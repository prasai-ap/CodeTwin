from app import database


def create_order(user_id: str, product_id: str, quantity: int, total_cents: int) -> dict[str, object]:
    order_id = f"order-{database.state['next_order_id']}"
    database.state["next_order_id"] += 1
    order = {
        "id": order_id,
        "user_id": user_id,
        "product_id": product_id,
        "quantity": quantity,
        "total_cents": total_cents,
        "status": "pending",
        "payment_id": None,
    }
    database.state["orders"][order_id] = order
    return order


def get_order(order_id: str) -> dict[str, object] | None:
    return database.state["orders"].get(order_id)


def update_order(order_id: str, **changes: object) -> dict[str, object]:
    order = database.state["orders"][order_id]
    order.update(changes)
    return order
