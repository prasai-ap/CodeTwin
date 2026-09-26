from fastapi import APIRouter, Header, HTTPException

from app.users.service import UsersService

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me")
def read_current_user(x_demo_user: str | None = Header(default=None, alias="X-Demo-User")) -> dict[str, object]:
    try:
        return {"user": UsersService().current_user(x_demo_user)}
    except PermissionError as error:
        raise HTTPException(status_code=401, detail=str(error)) from error
