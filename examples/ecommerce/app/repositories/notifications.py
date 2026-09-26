from app.database import db
from app.models import Notification


class NotificationsRepository:
    def create_payment_completed(self, user_id: str, order_id: str) -> Notification:
        db.notification_sequence += 1
        notification = Notification(
            f"notification-{db.notification_sequence}", user_id, order_id, "payment_completed"
        )
        db.notifications[notification.notification_id] = notification
        return notification

    def list_for_user(self, user_id: str) -> list[Notification]:
        return sorted(
            (item for item in db.notifications.values() if item.user_id == user_id),
            key=lambda item: item.notification_id,
        )
