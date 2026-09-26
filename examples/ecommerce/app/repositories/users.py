from app.database import db
from app.models import User


class UsersRepository:
    def get(self, user_id: str) -> User | None:
        return db.users.get(user_id)
