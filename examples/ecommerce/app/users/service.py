from app.auth.service import AuthenticationService
from app.models import User


class UsersService:
    def __init__(self, authentication: AuthenticationService | None = None) -> None:
        self.authentication = authentication or AuthenticationService()

    def current_user(self, user_id: str | None) -> User:
        return self.authentication.authenticate_demo_user(user_id)
