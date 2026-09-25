from app import database


def get_user(user_id: str) -> dict[str, str] | None:
    return database.state["users"].get(user_id)
