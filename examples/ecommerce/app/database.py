"""In-memory synthetic data store; no external or personal data is used."""

from app.models import Notification, Order, Payment, Product, User


class InMemoryDatabase:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.users = {"user-demo": User("user-demo", "Demo Developer")}
        self.products = {"product-demo": Product("product-demo", "CodeTwin Hoodie", 2500, 8)}
        self.orders: dict[str, Order] = {}
        self.payments: dict[str, Payment] = {}
        self.notifications: dict[str, Notification] = {}
        self.order_sequence = 0
        self.payment_sequence = 0
        self.notification_sequence = 0


db = InMemoryDatabase()
