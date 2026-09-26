from app.auth.session import require_demo_identity
from app.models.user import User
from app.repositories.users import UsersRepository


class AuthService:
    def __init__(self, users: UsersRepository | None = None) -> None:
        self.users = users or UsersRepository()

    def authenticate(self, user_id: str | None) -> User:
        return require_demo_identity(self.users.get(user_id or ""))
