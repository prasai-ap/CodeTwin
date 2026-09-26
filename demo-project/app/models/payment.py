from dataclasses import dataclass
from enum import StrEnum


class PaymentStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"


@dataclass(frozen=True)
class Payment:
    payment_id: str
    order_id: str
    user_id: str
    amount_cents: int
    status: PaymentStatus = PaymentStatus.PENDING
