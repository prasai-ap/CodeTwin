from app.models import Notification, Payment, PaymentStatus
from app.repositories.notifications import NotificationsRepository


class NotificationsService:
    """Downstream consumer that currently assumes one direct payment transition."""

    def __init__(self, notifications: NotificationsRepository | None = None) -> None:
        self.notifications = notifications or NotificationsRepository()

    def on_payment_transition(self, previous: Payment, current: Payment) -> None:
        if previous.status == PaymentStatus.PENDING and current.status == PaymentStatus.COMPLETED:
            self.notifications.create_payment_completed(current.user_id, current.order_id)

    def list_for_user(self, user_id: str) -> list[Notification]:
        return self.notifications.list_for_user(user_id)
