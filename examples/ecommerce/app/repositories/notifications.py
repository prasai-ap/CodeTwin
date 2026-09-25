from app import database


def add_notification(user_id: str, order_id: str, message: str) -> dict[str, str]:
    notification = {"user_id": user_id, "order_id": order_id, "message": message}
    database.state["notifications"].append(notification)
    return notification


def list_notifications(user_id: str) -> list[dict[str, str]]:
    return [item for item in database.state["notifications"] if item["user_id"] == user_id]
