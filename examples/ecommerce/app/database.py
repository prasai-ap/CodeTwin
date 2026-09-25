"""A tiny in-memory store standing in for a database in the demo fixture."""

from copy import deepcopy


INITIAL_STATE = {
    "users": {
        "user-1": {"id": "user-1", "email": "dev@example.test", "name": "Demo Developer"},
    },
    "products": {
        "product-1": {"id": "product-1", "name": "CodeTwin Hoodie", "price_cents": 2500, "stock": 8},
        "product-2": {"id": "product-2", "name": "CodeTwin Sticker Pack", "price_cents": 500, "stock": 20},
    },
    "orders": {},
    "payments": {},
    "notifications": [],
    "next_order_id": 1,
    "next_payment_id": 1,
}

state = deepcopy(INITIAL_STATE)


def reset_state() -> None:
    """Restore deterministic data between demo requests and tests."""
    global state
    state = deepcopy(INITIAL_STATE)
