from app.models.notification import Notification
from app.models.order import Order
from app.models.payment import Payment, PaymentStatus
from app.notifications.messages import payment_completed_message
from app.repositories.notifications import NotificationsRepository


class NotificationsService:
    def __init__(self, notifications: NotificationsRepository | None = None) -> None:
        self.notifications = notifications or NotificationsRepository()

    def on_payment_transition(
        self,
        previous: Payment,
        current: Payment,
        order: Order,
    ) -> Notification | None:
        # Legacy event contract: this subscriber still expects a one-step transition.
        if previous.status is not PaymentStatus.PENDING or current.status is not PaymentStatus.COMPLETED:
            return None
        return self.notifications.create(
            order.user_id,
            order.order_id,
            "payment_completed",
            payment_completed_message(order),
        )

    def list_for_user(self, user_id: str) -> list[Notification]:
        return self.notifications.list_for_user(user_id)
