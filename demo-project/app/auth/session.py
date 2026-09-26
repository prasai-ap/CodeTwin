"""Synthetic request identity policy."""

from app.models.user import User


def require_demo_identity(user: User | None) -> User:
    if user is None:
        raise LookupError("A valid X-Demo-User identity is required")
    return user
