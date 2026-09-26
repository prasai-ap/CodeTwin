from fastapi import APIRouter, Header, HTTPException

from app.services.auth_service import AuthService
from app.services.notifications_service import NotificationsService

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
def list_notifications(x_demo_user: str | None = Header(default=None)) -> dict[str, object]:
    try:
        user = AuthService().authenticate(x_demo_user)
    except LookupError as error:
        raise HTTPException(status_code=401, detail=str(error)) from error
    return {"notifications": NotificationsService().list_for_user(user.user_id)}
