"""Synthetic e-commerce domain models and payment states."""

from dataclasses import dataclass
from enum import StrEnum


class PaymentStatus(StrEnum):
    PENDING = "pending"
    AUTHORIZED = "authorized"
    COMPLETED = "completed"


@dataclass(frozen=True)
class User:
    user_id: str
    name: str


@dataclass(frozen=True)
class Product:
    product_id: str
    name: str
    unit_price_cents: int
    stock: int


@dataclass(frozen=True)
class Order:
    order_id: str
    user_id: str
    product_id: str
    quantity: int
    total_cents: int
    status: str = "pending"


@dataclass(frozen=True)
class Payment:
    payment_id: str
    order_id: str
    user_id: str
    amount_cents: int
    status: PaymentStatus = PaymentStatus.PENDING


@dataclass(frozen=True)
class Notification:
    notification_id: str
    user_id: str
    order_id: str
    event: str
