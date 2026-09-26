from app.models.user import User
from app.repositories.users import UsersRepository
from app.users.profile import public_profile


class UsersService:
    def __init__(self, users: UsersRepository | None = None) -> None:
        self.users = users or UsersRepository()

    def profile(self, user: User) -> dict[str, str]:
        return public_profile(user)

    def list_users(self) -> list[User]:
        return self.users.list()
