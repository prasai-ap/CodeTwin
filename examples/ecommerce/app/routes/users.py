from fastapi import APIRouter, Depends

from app.auth.service import require_user

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me")
def read_current_user(user: dict[str, str] = Depends(require_user)) -> dict[str, str]:
    return user
