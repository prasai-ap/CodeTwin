from fastapi import APIRouter, Depends

from app.auth.service import require_user

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.get("/session")
def read_session(user: dict[str, str] = Depends(require_user)) -> dict[str, str]:
    return {"user_id": user["id"], "authenticated": "true"}
