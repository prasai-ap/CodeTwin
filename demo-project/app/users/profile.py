"""Small profile helpers shared by user-facing services."""

from app.models.user import User


def public_profile(user: User) -> dict[str, str]:
    return {"user_id": user.user_id, "name": user.name, "email": user.email}
