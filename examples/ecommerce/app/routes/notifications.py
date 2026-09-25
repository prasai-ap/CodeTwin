from fastapi import APIRouter, Depends

from app.auth.service import require_user
from app.repositories.notifications import list_notifications

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
def read_notifications(user: dict[str, str] = Depends(require_user)) -> list[dict[str, str]]:
    return list_notifications(user["id"])
