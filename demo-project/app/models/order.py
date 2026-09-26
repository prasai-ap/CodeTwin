from dataclasses import dataclass
from enum import StrEnum


class OrderStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"


@dataclass(frozen=True)
class Order:
    order_id: str
    user_id: str
    product_id: str
    quantity: int
    total_cents: int
    status: OrderStatus = OrderStatus.PENDING
