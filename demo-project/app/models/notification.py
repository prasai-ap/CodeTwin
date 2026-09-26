from dataclasses import dataclass


@dataclass(frozen=True)
class Notification:
    notification_id: str
    user_id: str
    order_id: str
    event: str
    message: str
