from fastapi import APIRouter, Header, HTTPException

from app.auth.service import AuthenticationService
from app.notifications.service import NotificationsService

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
def list_notifications(x_demo_user: str | None = Header(default=None, alias="X-Demo-User")) -> dict[str, object]:
    try:
        user = AuthenticationService().authenticate_demo_user(x_demo_user)
    except PermissionError as error:
        raise HTTPException(status_code=401, detail=str(error)) from error
    return {"notifications": NotificationsService().list_for_user(user.user_id)}
