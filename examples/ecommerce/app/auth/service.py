"""Header-based identity lookup for the synthetic API."""

from fastapi import Header, HTTPException

from app.repositories.users import get_user


def require_user(x_user_id: str | None = Header(default=None)) -> dict[str, str]:
    if not x_user_id:
        raise HTTPException(status_code=401, detail="X-User-ID header is required")
    user = get_user(x_user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Unknown user")
    return user
