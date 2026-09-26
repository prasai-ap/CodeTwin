from app.models.notification import Notification
from app.models.order import Order
from app.notifications.messages import payment_completed_message
from app.repositories.notifications import NotificationsRepository


class NotificationsService:
    def __init__(self, notifications: NotificationsRepository | None = None) -> None:
        self.notifications = notifications or NotificationsRepository()

    def send_payment_completed(self, order: Order) -> Notification:
        return self.notifications.create(
            order.user_id,
            order.order_id,
            "payment_completed",
            payment_completed_message(order),
        )

    def list_for_user(self, user_id: str) -> list[Notification]:
        return self.notifications.list_for_user(user_id)
