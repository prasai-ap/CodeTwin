from fastapi import APIRouter, Header, HTTPException

from app.services.auth_service import AuthService
from app.services.users_service import UsersService

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me")
def read_my_profile(x_demo_user: str | None = Header(default=None)) -> dict[str, object]:
    try:
        user = AuthService().authenticate(x_demo_user)
    except LookupError as error:
        raise HTTPException(status_code=401, detail=str(error)) from error
    return {"user": UsersService().profile(user)}
