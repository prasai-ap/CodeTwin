from app.models import User
from app.repositories.users import UsersRepository


class AuthenticationService:
    def __init__(self, users: UsersRepository | None = None) -> None:
        self.users = users or UsersRepository()

    def authenticate_demo_user(self, user_id: str | None) -> User:
        if not user_id:
            raise PermissionError("Provide the X-Demo-User header")
        user = self.users.get(user_id)
        if user is None:
            raise PermissionError("Unknown demo user")
        return user
