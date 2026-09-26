from app.database import db
from app.models.notification import Notification


class NotificationsRepository:
    def create(self, user_id: str, order_id: str, event: str, message: str) -> Notification:
        db.notification_sequence += 1
        notification = Notification(
            f"notification-{db.notification_sequence:04d}", user_id, order_id, event, message
        )
        db.notifications[notification.notification_id] = notification
        return notification

    def list_for_user(self, user_id: str) -> list[Notification]:
        return [item for item in db.notifications.values() if item.user_id == user_id]
