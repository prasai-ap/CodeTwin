"""In-memory store populated only with synthetic demo records."""

from app.models.notification import Notification
from app.models.order import Order
from app.models.payment import Payment
from app.models.product import Product
from app.models.user import User


class InMemoryDatabase:
    def reset(self) -> None:
        self.users = {
            "user-ada": User("user-ada", "Ada Example", "ada@example.test"),
            "user-grace": User("user-grace", "Grace Example", "grace@example.test"),
        }
        self.products = {
            "product-keyboard": Product("product-keyboard", "Mechanical Keyboard", 8900, 12, "accessories"),
            "product-notebook": Product("product-notebook", "Developer Notebook", 1200, 30, "stationery"),
        }
        self.orders: dict[str, Order] = {}
        self.payments: dict[str, Payment] = {}
        self.notifications: dict[str, Notification] = {}
        self.order_sequence = 0
        self.payment_sequence = 0
        self.notification_sequence = 0

    def __init__(self) -> None:
        self.reset()


db = InMemoryDatabase()
